from fastapi import APIRouter, Query
from typing import List, Optional
from app.services.weeek import WeeekClient

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])

@router.get("/weeek/tasks")
async def get_weeek_tasks(
    project_id: Optional[int] = Query(None, alias="projectId"),
    board_id: Optional[int] = Query(None, alias="boardId"),
    tags: Optional[List[int]] = Query(None),
    tag_names: Optional[List[str]] = Query(None, alias="tagNames"),
):
    """
    Proxy endpoint for Weeek tasks.
    """
    client = WeeekClient()
    return await client.get_tasks(project_id, board_id, tags, tag_names)

@router.get("/weeek/discovery")
async def discover_weeek_ids(project_id: Optional[int] = Query(None, alias="projectId")):
    """
    Helper endpoint to list boards and projects to find their IDs.
    """
    client = WeeekClient()
    workspaces = await client.get_workspaces()
    me = await client.get_me()
    boards = await client.get_boards(project_id)
    projects = await client.get_projects()
    tags = await client.get_tags()
    members = await client.get_members()
    return {
        "workspaces": workspaces,
        "me": me,
        "boards": boards,
        "projects": projects,
        "tags": tags,
        "members": members,
        "hint": "Check tasks response to see tag IDs associated with them."
    }
