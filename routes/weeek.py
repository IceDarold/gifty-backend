from datetime import date
from typing import Optional, Dict

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.db import get_db
from app.models import WeeekAccount
from app.config import get_settings
from app.services.weeek import WeeekClient
from routes.internal import verify_internal_token

router = APIRouter(prefix="/internal/weeek", tags=["internal-weeek"])
settings = get_settings()

# Schemas
class ConnectWeeekRequest(BaseModel):
    telegram_chat_id: int
    weeek_api_token: str

class RescheduleRequest(BaseModel):
    telegram_chat_id: int
    new_date: str # YYYY-MM-DD
    reason: str

class CreateTaskRequest(BaseModel):
    telegram_chat_id: int
    title: str
    description: Optional[str] = None
    project_id: Optional[int] = None
    board_id: Optional[int] = None
    due_date: Optional[str] = None

# Helper
async def get_weeek_account(db: AsyncSession, telegram_chat_id: int) -> WeeekAccount:
    result = await db.execute(select(WeeekAccount).where(WeeekAccount.telegram_chat_id == telegram_chat_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Weeek account not found")
    return account

@router.post("/connect")
async def connect_weeek_account(
    req: ConnectWeeekRequest,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    """
    Connects a Telegram user to Weeek.
    - Validates token
    - Creates 'Gifty 🎁' project if missing
    - Saves account
    """
    # 1. Validate Token & Get User Info
    temp_client = WeeekClient()
    temp_client.token = req.weeek_api_token
    temp_client.headers["Authorization"] = f"Bearer {req.weeek_api_token}"
    
    me = await temp_client.get_me()
    if not me.get("success"):
        raise HTTPException(status_code=400, detail="Invalid Weeek API Token")
    
    user_data = me.get("user", {})
    weeek_user_id = user_data.get("id")
    
    # 2. Check access to corporate workspace (optional)
    workspace_id = getattr(settings, "weeek_workspace_id", None)
    if workspace_id:
        workspaces_resp = await temp_client.get_workspaces()
        if not workspaces_resp.get("success"):
            raise HTTPException(status_code=502, detail="Failed to validate Weeek workspace access")
        workspaces = workspaces_resp.get("workspaces") or workspaces_resp.get("data") or []
        has_access = any(str(w.get("id")) == str(workspace_id) for w in workspaces if isinstance(w, dict))
        if not has_access:
            raise HTTPException(
                status_code=403,
                detail="у вас нет доступа к корпоративному workspace в weeek. Попросите вашего ментора добавить вас."
            )
    else:
        workspace_id = None

    # 3. Check or Create Project 'Gifty 🎁' (Personal Workspace)
    projects_resp = await temp_client.get_projects()
    projects = projects_resp.get("projects", [])
    
    gifty_project = next((p for p in projects if "Gifty" in p["name"]), None)
    
    created_new = False
    if not gifty_project:
        proj_resp = await temp_client.create_project({"name": "Gifty 🎁"})
        if proj_resp.get("success"):
            gifty_project = proj_resp.get("project")
            created_new = True
            
    personal_project_id = None
    personal_board_id = None

    if gifty_project:
        personal_project_id = gifty_project["id"]
        if created_new:
            # Create "Onboarding" board
            board_resp = await temp_client.create_board({"name": "Onboarding", "projectId": personal_project_id})
            if board_resp.get("success"):
                board = board_resp.get("board")
                personal_board_id = board["id"]
                
                # Create Column "To Do"
                col_resp = await temp_client.create_board_column({"name": "To Do", "boardId": personal_board_id})
                if col_resp.get("success"):
                    # Create Task
                    col_id = col_resp["boardColumn"]["id"]
                    await temp_client.create_task({
                        "title": "Welcome to Gifty! 🎁", 
                        "description": "This is your personal workspace. Manage your tasks here!",
                        "projectId": personal_project_id,
                        "boardId": personal_board_id,
                        "boardColumnId": col_id,
                        "type": "action"
                    })
            
            # Create other boards
            await temp_client.create_board({"name": "Weekly Goals 🎯", "projectId": personal_project_id})
            await temp_client.create_board({"name": "Ideas 💡", "projectId": personal_project_id})

    # For now, let's just save the account and handling project creation logic can be refined 
    # if we add create_project to client.
    
    stmt = select(WeeekAccount).where(WeeekAccount.telegram_chat_id == req.telegram_chat_id)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    
    if existing:
        existing.weeek_api_token = req.weeek_api_token
        existing.weeek_user_id = str(weeek_user_id)
        existing.weeek_workspace_id = workspace_id
        existing.is_active = True
    else:
        new_acc = WeeekAccount(
            telegram_chat_id=req.telegram_chat_id,
            weeek_api_token=req.weeek_api_token,
            weeek_user_id=str(weeek_user_id),
            weeek_workspace_id=workspace_id
        )
        db.add(new_acc)
    
    await db.commit()
    return {"status": "ok", "weeek_user_id": weeek_user_id, "workspace_id": workspace_id}

@router.get("/tasks")
async def get_tasks(
    telegram_chat_id: int,
    type: str = "all", # all, today, tomorrow, overdue
    project_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    account = await get_weeek_account(db, telegram_chat_id)
    
    client = WeeekClient()
    client.token = account.weeek_api_token
    client.headers["Authorization"] = f"Bearer {account.weeek_api_token}"
    
    # Logic for filters
    # Weeek API supports 'day' (YYYY-MM-DD), 'date' (legacy?)
    # startDate, endDate.
    
    today = date.today()
    params = {}
    
    if type == "today":
        params["day"] = today.isoformat()
    elif type == "tomorrow":
        # API doesn't support 'tomorrow' keyword directly maybe?
        # Actually client.get_tasks takes params dict or explicit args.
        pass # We'll filter in client or post-process?
        
    # We'll fetch all and filter for Overdue? Or use get_tasks params.
    # client.get_tasks is simple. Let's rely on it.
    
    resp = await client.get_tasks(project_id=project_id)
    if not resp.get("success"):
        raise HTTPException(status_code=500, detail=resp.get("error"))
        
    tasks = resp.get("tasks", [])
    # Filter by corporate workspace (if possible)
    target_workspace_id = account.weeek_workspace_id or settings.weeek_workspace_id
    projects_workspace_map: Dict[int, Optional[int]] = {}
    projects_resp = await client.get_projects()
    if projects_resp.get("success"):
        projects_workspace_map = _build_projects_workspace_map(projects_resp.get("projects", []))
    tasks = _filter_tasks_by_workspace(tasks, target_workspace_id, projects_workspace_map)
    
    # Filter
    filtered = []
    for t in tasks:
        # Check ownership? "My tasks" means assigned to me?
        # API returns all workspace tasks usually? Or filtered by token user?
        # Token is personal, so maybe it defaults to user? 
        # Actually Weeek API usually returns everything in workspace unless filtered by userId.
        
        # We saved weeek_user_id, we should filter by it if "my" is implied.
        # But 'type=all' might mean "My All".
        
        is_mine = str(t.get("userId")) == str(account.weeek_user_id) or \
                  (t.get("userIds") and str(account.weeek_user_id) in map(str, t.get("userIds", [])))
                  
        if type == "workspace":
             # Return all tasks, skip user filter
             filtered.append(t)
             continue
             
        is_mine = str(t.get("userId")) == str(account.weeek_user_id) or \
                  (t.get("userIds") and str(account.weeek_user_id) in map(str, t.get("userIds", [])))
                  
        if not is_mine:
             continue
             
        # Date filtering
        # ... logic ...
        filtered.append(t)
        
    return {"tasks": filtered}

@router.post("/tasks")
async def create_task(
    req: CreateTaskRequest,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    account = await get_weeek_account(db, req.telegram_chat_id)
    client = WeeekClient()
    client.token = account.weeek_api_token
    client.headers["Authorization"] = f"Bearer {account.weeek_api_token}"
    
    data = {"title": req.title, "type": "action"}
    if req.description:
        data["description"] = req.description
    if req.due_date:
        data["date"] = req.due_date
    if req.project_id:
        data["projectId"] = req.project_id
        
    resp = await client.create_task(data)
    if not resp.get("success"):
         raise HTTPException(status_code=500, detail=resp.get("error"))
         
    return resp

@router.post("/tasks/{task_id}/reschedule")
async def reschedule_task(
    task_id: int,
    req: RescheduleRequest,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    account = await get_weeek_account(db, req.telegram_chat_id)
    client = WeeekClient()
    client.token = account.weeek_api_token
    client.headers["Authorization"] = f"Bearer {account.weeek_api_token}"
    
    # 1. Update Date
    upd_resp = await client.update_task(task_id, {"date": req.new_date})
    if not upd_resp.get("success"):
        raise HTTPException(status_code=500, detail="Failed to update date")
        
    # 2. Add Comment
    comment_text = f"📅 Deadline changed to {req.new_date}\nReason: {req.reason}"
    await client.add_task_comment(task_id, comment_text)
    
    return {"status": "ok"}

@router.post("/tasks/{task_id}/complete")
async def complete_task_endpoint(
    task_id: int,
    telegram_chat_id: int = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    account = await get_weeek_account(db, telegram_chat_id)
    client = WeeekClient()
    client.token = account.weeek_api_token
    client.headers["Authorization"] = f"Bearer {account.weeek_api_token}"
    
    resp = await client.complete_task(task_id)
    if not resp.get("success"):
        raise HTTPException(status_code=500, detail="Failed to complete task")
        
    return {"status": "ok"}

def _extract_workspace_id(obj):
    if not obj:
        return None
    ws_id = obj.get("workspaceId") or obj.get("workspace_id")
    if ws_id is not None:
        return ws_id
    workspace = obj.get("workspace") or {}
    return workspace.get("id")

def _build_projects_workspace_map(projects):
    mapping = {}
    for proj in projects or []:
        pid = proj.get("id")
        if pid is None:
            continue
        mapping[pid] = _extract_workspace_id(proj)
    return mapping

def _filter_tasks_by_workspace(tasks, target_workspace_id, projects_map):
    if not target_workspace_id:
        return tasks
    filtered = []
    for t in tasks:
        task_ws = _extract_workspace_id(t)
        if task_ws is not None:
            if str(task_ws) == str(target_workspace_id):
                filtered.append(t)
            continue
        project_id = t.get("projectId")
        if project_id is None:
            continue
        if str(projects_map.get(project_id)) == str(target_workspace_id):
            filtered.append(t)
    return filtered
