
import logging
from datetime import datetime, timedelta, date, time
from app.db import get_session_context
from sqlalchemy import select
from app.models import WeeekAccount
from app.services.weeek import WeeekClient
from app.services.notifications import get_notification_service

from app.config import get_settings

logger = logging.getLogger(__name__)

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
async def run_weeek_reminders():
    """
    Check for Weeek reminders and send notifications.
    Suggested schedule: Hourly.
    """
    logger.info("Starting Weeek reminders check...")
    
    current_time_utc = datetime.utcnow()
    # Assuming server time is UTC, and user wants 'reminder_time' (local).
    # MVP: Assume Moscow time (+3).
    # Proper: Use account.timezone (defaults to Europe/Moscow).
    # For MVP simplicity: We check all users. If user's local time matches logic, send.
    
    moscow_now = current_time_utc + timedelta(hours=3)
    current_hour = moscow_now.hour
    
    # Logic:
    # 09:00 -> Daily Digest + Deadline Today
    # 10:00 -> Overdue
    # 18:00 -> Deadline Tomorrow
    
    async with get_session_context() as session:
        result = await session.execute(select(WeeekAccount).where(WeeekAccount.is_active == True))
        accounts = result.scalars().all()
        
        notification_service = get_notification_service()
        
        for acc in accounts:
            # MVP: Hardcoded scheduling for everyone based on Moscow time.
            # Real impl would check acc.timezone and match acc.reminder_time.
            
            client = WeeekClient()
            client.token = acc.weeek_api_token
            client.headers["Authorization"] = f"Bearer {acc.weeek_api_token}"
            
            # Fetch tasks (My tasks)
            # Optimization: We could fetch with date range params if API supported well, 
            # but getting all my tasks is safer for filters.
            tasks_resp = await client.get_tasks()
            if not tasks_resp.get("success"):
                logger.error(f"Failed to fetch tasks for user {acc.telegram_chat_id}")
                continue
                
            tasks = tasks_resp.get("tasks", [])
            target_workspace_id = acc.weeek_workspace_id or get_settings().weeek_workspace_id
            if target_workspace_id:
                projects_resp = await client.get_projects()
                projects_map = {}
                if projects_resp.get("success"):
                    projects_map = _build_projects_workspace_map(projects_resp.get("projects", []))
                filtered_tasks = []
                for t in tasks:
                    task_ws = _extract_workspace_id(t)
                    if task_ws is not None:
                        if str(task_ws) == str(target_workspace_id):
                            filtered_tasks.append(t)
                        continue
                    project_id = t.get("projectId")
                    if project_id is None:
                        continue
                    if str(projects_map.get(project_id)) == str(target_workspace_id):
                        filtered_tasks.append(t)
                tasks = filtered_tasks
            my_tasks = []
            for t in tasks:
                 is_mine = str(t.get("userId")) == str(acc.weeek_user_id) or \
                           (t.get("userIds") and str(acc.weeek_user_id) in map(str, t.get("userIds", [])))
                 if is_mine and not t.get("isCompleted"):
                     my_tasks.append(t)

            today_iso = date.today().isoformat()
            tomorrow_iso = (date.today() + timedelta(days=1)).isoformat()
            
            # 1. Digest & Deadline Today (09:00)
            if current_hour == 9:
                due_today = [t for t in my_tasks if t.get("date") == today_iso]
                if due_today:
                    msg = "🌅 *Daily Digest: Tasks for Today*\n\n"
                    for t in due_today:
                        msg += f"• {t['title']} (Due: {t.get('time') or 'All day'})\n"
                    
                    await notification_service.notify(
                        "private", 
                        msg, 
                        data={"target_chat_id": acc.telegram_chat_id}
                    )
            
            # 2. Overdue (10:00)
            if current_hour == 10:
                overdue = [t for t in my_tasks if t.get("date") and t.get("date") < today_iso]
                if overdue:
                     msg = "⚠️ *Overdue Tasks Warning*\n\n"
                     for t in overdue:
                         msg += f"• {t['title']} (Due: {t['date']})\n"
                     
                     await notification_service.notify(
                        "private", 
                        msg, 
                        data={"target_chat_id": acc.telegram_chat_id}
                     )

            # 3. Deadline Tomorrow (18:00)
            if current_hour == 18:
                due_tomorrow = [t for t in my_tasks if t.get("date") == tomorrow_iso]
                if due_tomorrow:
                    msg = "📅 *Upcoming: Tasks for Tomorrow*\n\n"
                    for t in due_tomorrow:
                        msg += f"• {t['title']}\n"
                    
                    await notification_service.notify(
                        "private", 
                        msg, 
                        data={"target_chat_id": acc.telegram_chat_id}
                    )
    
    logger.info("Weeek reminders check completed.")
