import httpx
import logging
from typing import List, Dict, Any, Optional
from app.config import get_settings

logger = logging.getLogger(__name__)

class WeeekClient:
    def __init__(self):
        settings = get_settings()
        self.base_url = str(settings.weeek_api_base).rstrip("/")
        self.token = settings.weeek_api_token
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    async def get_tasks(
        self, 
        project_id: Optional[int] = None, 
        board_id: Optional[int] = None, 
        tags: Optional[List[int]] = None,
        tag_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Fetch tasks from Weeek API.
        """
        if not self.token:
            logger.warning("WEEEK_API_TOKEN not set, fallback to mock mode.")
            return self._get_mock_tasks(tags)

        # Resolve tag names to IDs if provided
        resolved_tag_ids = list(tags) if tags else []
        if tag_names:
            # Flatten and split by comma in case a single string item contains multiple names
            flat_tag_names = []
            for tn in tag_names:
                flat_tag_names.extend([name.strip() for name in tn.split(",") if name.strip()])
            
            all_tags_resp = await self.get_tags()
            if all_tags_resp.get("success"):
                all_tags = all_tags_resp.get("tags", [])
                for name in flat_tag_names:
                    tid = next((t["id"] for t in all_tags if t["title"].lower() == name.lower()), None)
                    if tid is not None:
                        resolved_tag_ids.append(tid)

        params = {}
        if project_id:
            params["projectId"] = project_id
        if board_id:
            params["boardId"] = board_id
        
        # If we use a list, httpx will send multiple 'tags' parameters if we pass it correctly
        # However, Weeek might expect 'tags[]' or repeated 'tags'.
        # Let's try repeated 'tags' first.
        
        url = f"{self.base_url}/tm/tasks"
        if resolved_tag_ids:
            # Try tags[] format
            params_list = [(k, v) for k, v in params.items()]
            for tid in resolved_tag_ids:
                params_list.append(("tags[]", tid))
            params = params_list

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url,
                    headers=self.headers,
                    params=params
                )
                if response.status_code == 401:
                    logger.error("Weeek API Unauthorized - check token.")
                    return {"success": False, "error": "Unauthorized"}
                
                if not response.is_success:
                    return {"success": False, "error": f"Status {response.status_code}: {response.text}"}

                data = response.json()
                
                # Fetch members to map IDs
                members_resp = await self.get_members()
                members_map = {}
                if members_resp.get("success"):
                   for m in members_resp.get("members", []):
                       members_map[m["id"]] = {
                           "logo": m.get("logo"),
                           "firstName": m.get("firstName"),
                           "lastName": m.get("lastName")
                       }

                # Fetch columns for relevant boards
                tasks_list = data.get("tasks", [])
                unique_board_ids = set(t.get("boardId") for t in tasks_list if t.get("boardId"))
                
                columns_map = {}
                for bid in unique_board_ids:
                    # We might want to cache this or do it in parallel, but for now sequential is fine for small number of boards
                     cols_resp = await self.get_board_columns(bid)
                     if cols_resp.get("success"):
                         for col in cols_resp.get("boardColumns", []):
                             columns_map[col["id"]] = col["name"]

                # Normalize response for our frontend
                if data.get("success"):
                    return {
                        "success": True,
                        "tasks": tasks_list,
                        "hasMore": data.get("hasMore", False),
                        "workspaceId": get_settings().weeek_workspace_id,
                        "members": members_map,
                        "columns": columns_map
                    }
                return {"success": False, "error": "API returned failure"}
            except Exception as e:
                logger.error(f"Error fetching tasks from Weeek: {e}")
                return {"success": False, "error": str(e)}

    async def get_boards(self, project_id: Optional[int] = None) -> Dict[str, Any]:
        """Fetch all boards."""
        if not self.token:
            return {"success": False, "error": "Token missing"}
        
        params = {}
        if project_id:
            params["projectId"] = project_id
            
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/tm/boards",
                    headers=self.headers,
                    params=params
                )
                if not response.is_success:
                    return {"success": False, "error": f"Status {response.status_code}: {response.text}"}
                return response.json()
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def get_projects(self) -> Dict[str, Any]:
        """Fetch all projects."""
        if not self.token:
            return {"success": False, "error": "Token missing"}
            
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/tm/projects",
                    headers=self.headers
                )
                if not response.is_success:
                    return {"success": False, "error": f"Status {response.status_code}: {response.text}"}
                return response.json()
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def get_me(self) -> Dict[str, Any]:
        """Fetch current user info."""
        if not self.token:
            return {"success": False, "error": "Token missing"}
            
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/users/me",
                    headers=self.headers
                )
                if not response.is_success:
                    return {"success": False, "error": f"Status {response.status_code}: {response.text}"}
                return response.json()
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def get_workspaces(self) -> Dict[str, Any]:
        """Fetch all workspaces."""
        if not self.token:
            return {"success": False, "error": "Token missing"}
            
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/tm/workspaces",
                    headers=self.headers
                )
                if not response.is_success:
                    return {"success": False, "error": f"Status {response.status_code}: {response.text}"}
                return response.json()
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def get_members(self) -> Dict[str, Any]:
        """Fetch workspace members."""
        if not self.token:
            return {"success": False, "error": "Token missing"}
            
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/ws/members",
                    headers=self.headers
                )
                if not response.is_success:
                    return {"success": False, "error": f"Status {response.status_code}: {response.text}"}
                return response.json()
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def get_tags(self) -> Dict[str, Any]:
        """Fetch all workspace tags."""
        if not self.token:
            return {"success": False, "error": "Token missing"}
            
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/ws/tags",
                    headers=self.headers
                )
                if not response.is_success:
                    return {"success": False, "error": f"Status {response.status_code}: {response.text}"}
                return response.json()
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def create_task(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new task."""
        if not self.token:
            return {"success": False, "error": "Token missing"}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/tm/tasks",
                    headers=self.headers,
                    json=data
                )
                if not response.is_success:
                    return {"success": False, "error": f"Status {response.status_code}: {response.text}"}
                return response.json()
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def complete_task(self, task_id: int) -> Dict[str, Any]:
        """Mark task as completed."""
        if not self.token:
            return {"success": False, "error": "Token missing"}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/tm/tasks/{task_id}/complete",
                    headers=self.headers,
                    json="completed"
                )
                if not response.is_success:
                    return {"success": False, "error": f"Status {response.status_code}: {response.text}"}
                return response.json()
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def create_board(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new board."""
        if not self.token:
            return {"success": False, "error": "Token missing"}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/tm/boards",
                    headers=self.headers,
                    json=data
                )
                if not response.is_success:
                    return {"success": False, "error": f"Status {response.status_code}: {response.text}"}
                return response.json()
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def create_tag(self, title: str, color: Optional[str] = None) -> Dict[str, Any]:
        """Create a new workspace tag."""
        if not self.token:
            return {"success": False, "error": "Token missing"}
        data = {"title": title}
        if color:
            data["color"] = color
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/ws/tags",
                    headers=self.headers,
                    json=data
                )
                if not response.is_success:
                    return {"success": False, "error": f"Status {response.status_code}: {response.text}"}
                return response.json()
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def get_task(self, task_id: int) -> Dict[str, Any]:
        """Fetch a single task by ID."""
        if not self.token:
            return {"success": False, "error": "Token missing"}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/tm/tasks/{task_id}",
                    headers=self.headers
                )
                if not response.is_success:
                    return {"success": False, "error": f"Status {response.status_code}: {response.text}"}
                return response.json()
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def uncomplete_task(self, task_id: int) -> Dict[str, Any]:
        """Un-mark task as completed."""
        if not self.token:
            return {"success": False, "error": "Token missing"}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/tm/tasks/{task_id}/un-complete",
                    headers=self.headers,
                    json="action"
                )
                if not response.is_success:
                    return {"success": False, "error": f"Status {response.status_code}: {response.text}"}
                return response.json()
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def delete_task(self, task_id: int) -> Dict[str, Any]:
        """Delete a task."""
        if not self.token:
            return {"success": False, "error": "Token missing"}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.delete(
                    f"{self.base_url}/tm/tasks/{task_id}",
                    headers=self.headers
                )
                if not response.is_success:
                    return {"success": False, "error": f"Status {response.status_code}: {response.text}"}
                return response.json()
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def change_task_board(self, task_id: int, board_id: int) -> Dict[str, Any]:
        """Move task to another board."""
        if not self.token:
            return {"success": False, "error": "Token missing"}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/tm/tasks/{task_id}/board",
                    headers=self.headers,
                    json={"boardId": board_id}
                )
                if not response.is_success:
                    return {"success": False, "error": f"Status {response.status_code}: {response.text}"}
                return response.json()
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def change_task_column(self, task_id: int, column_id: int) -> Dict[str, Any]:
        """Move task to another board column."""
        if not self.token:
            return {"success": False, "error": "Token missing"}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/tm/tasks/{task_id}/board-column",
                    headers=self.headers,
                    json={"boardColumnId": column_id}
                )
                if not response.is_success:
                    return {"success": False, "error": f"Status {response.status_code}: {response.text}"}
                return response.json()
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def add_task_location(self, task_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Add task to a project/board/column."""
        if not self.token:
            return {"success": False, "error": "Token missing"}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/tm/tasks/{task_id}/locations",
                    headers=self.headers,
                    json=data
                )
                if not response.is_success:
                    return {"success": False, "error": f"Status {response.status_code}: {response.text}"}
                return response.json()
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def remove_task_location(self, task_id: int, project_id: int) -> Dict[str, Any]:
        """Remove task from a project."""
        if not self.token:
            return {"success": False, "error": "Token missing"}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(
                    "DELETE",
                    f"{self.base_url}/tm/tasks/{task_id}/locations",
                    headers=self.headers,
                    json={"projectId": project_id}
                )
                if not response.is_success:
                    return {"success": False, "error": f"Status {response.status_code}: {response.text}"}
                return response.json()
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def add_task_assignees(self, task_id: int, assignees: List[str]) -> Dict[str, Any]:
        """Add assignees to a task."""
        if not self.token:
            return {"success": False, "error": "Token missing"}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/tm/tasks/{task_id}/assignees",
                    headers=self.headers,
                    json={"assignees": assignees}
                )
                if not response.is_success:
                    return {"success": False, "error": f"Status {response.status_code}: {response.text}"}
                return response.json()
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def remove_task_assignees(self, task_id: int, assignees: List[str]) -> Dict[str, Any]:
        """Remove assignees from a task."""
        if not self.token:
            return {"success": False, "error": "Token missing"}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(
                    "DELETE",
                    f"{self.base_url}/tm/tasks/{task_id}/assignees",
                    headers=self.headers,
                    json={"assignees": assignees}
                )
                if not response.is_success:
                    return {"success": False, "error": f"Status {response.status_code}: {response.text}"}
                return response.json()
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def get_board_columns(self, board_id: Optional[int] = None) -> Dict[str, Any]:
        """Fetch all board columns."""
        if not self.token:
            return {"success": False, "error": "Token missing"}
        params = {}
        if board_id:
            params["boardId"] = board_id
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/tm/board-columns",
                    headers=self.headers,
                    params=params
                )
                if not response.is_success:
                    return {"success": False, "error": f"Status {response.status_code}: {response.text}"}
                return response.json()
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def create_board_column(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new board column."""
        if not self.token:
            return {"success": False, "error": "Token missing"}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/tm/board-columns",
                    headers=self.headers,
                    json=data
                )
                if not response.is_success:
                    return {"success": False, "error": f"Status {response.status_code}: {response.text}"}
                return response.json()
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def update_board_column(self, column_id: int, name: str) -> Dict[str, Any]:
        """Update a board column."""
        if not self.token:
            return {"success": False, "error": "Token missing"}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.put(
                    f"{self.base_url}/tm/board-columns/{column_id}",
                    headers=self.headers,
                    json={"name": name}
                )
                if not response.is_success:
                    return {"success": False, "error": f"Status {response.status_code}: {response.text}"}
                return response.json()
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def delete_board_column(self, column_id: int) -> Dict[str, Any]:
        """Delete a board column."""
        if not self.token:
            return {"success": False, "error": "Token missing"}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.delete(
                    f"{self.base_url}/tm/board-columns/{column_id}",
                    headers=self.headers
                )
                if not response.is_success:
                    return {"success": False, "error": f"Status {response.status_code}: {response.text}"}
                return response.json()
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def move_board_column(self, column_id: int, upper_column_id: int) -> Dict[str, Any]:
        """Move a board column."""
        if not self.token:
            return {"success": False, "error": "Token missing"}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/tm/board-columns/{column_id}/move",
                    headers=self.headers,
                    json={"upperBoardColumnId": upper_column_id}
                )
                if not response.is_success:
                    return {"success": False, "error": f"Status {response.status_code}: {response.text}"}
                return response.json()
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def delete_board(self, board_id: int) -> Dict[str, Any]:
        """Delete a board."""
        if not self.token:
            return {"success": False, "error": "Token missing"}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.delete(
                    f"{self.base_url}/tm/boards/{board_id}",
                    headers=self.headers
                )
                if not response.is_success:
                    return {"success": False, "error": f"Status {response.status_code}: {response.text}"}
                return response.json()
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def move_board(self, board_id: int, upper_board_id: int) -> Dict[str, Any]:
        """Move a board."""
        if not self.token:
            return {"success": False, "error": "Token missing"}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/tm/boards/{board_id}/move",
                    headers=self.headers,
                    json={"upperBoardId": upper_board_id}
                )
                if not response.is_success:
                    return {"success": False, "error": f"Status {response.status_code}: {response.text}"}
                return response.json()
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def update_task(self, task_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing task."""
        if not self.token:
            return {"success": False, "error": "Token missing"}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.put(
                    f"{self.base_url}/tm/tasks/{task_id}",
                    headers=self.headers,
                    json=data
                )
                if not response.is_success:
                    return {"success": False, "error": f"Status {response.status_code}: {response.text}"}
                return response.json()
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def get_task_comments(self, task_id: int) -> Dict[str, Any]:
        """Fetch task comments."""
        if not self.token:
            return {"success": False, "error": "Token missing"}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/tm/tasks/{task_id}/comments",
                    headers=self.headers
                )
                if not response.is_success:
                    return {"success": False, "error": f"Status {response.status_code}: {response.text}"}
                return response.json()
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def add_task_comment(self, task_id: int, text: str) -> Dict[str, Any]:
        """Add a comment to a task."""
        if not self.token:
            return {"success": False, "error": "Token missing"}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/tm/tasks/{task_id}/comments",
                    headers=self.headers,
                    json={"text": text}
                )
                if not response.is_success:
                    return {"success": False, "error": f"Status {response.status_code}: {response.text}"}
                return response.json()
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def get_subtasks(self, task_id: int) -> Dict[str, Any]:
        """Fetch subtasks of a task."""
        if not self.token:
            return {"success": False, "error": "Token missing"}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/tm/tasks/{task_id}/subtasks",
                    headers=self.headers
                )
                if not response.is_success:
                    return {"success": False, "error": f"Status {response.status_code}: {response.text}"}
                return response.json()
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def get_custom_fields(self) -> Dict[str, Any]:
        """Fetch all custom fields."""
        if not self.token:
            return {"success": False, "error": "Token missing"}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/tm/custom-fields",
                    headers=self.headers
                )
                if not response.is_success:
                    return {"success": False, "error": f"Status {response.status_code}: {response.text}"}
                return response.json()
            except Exception as e:
                return {"success": False, "error": str(e)}

    def _get_mock_tasks(self, tags: Optional[List[int]] = None) -> Dict[str, Any]:
        """Returns mock tasks for testing when API token is not set."""
        mock_tasks = [
            {
                "id": 1,
                "title": "Реализовать Scrapy Worker",
                "isCompleted": True,
                "tags": [101] # Assume 101 is 'parsing'
            },
            {
                "id": 2,
                "title": "Интеграция с RabbitMQ",
                "isCompleted": True,
                "tags": [101]
            },
            {
                "id": 3,
                "title": "Ротация прокси и User-Agent",
                "isCompleted": False,
                "tags": [101]
            },
            {
                "id": 4,
                "title": "Смарт-планировщик (Adaptive Intervals)",
                "isCompleted": False,
                "tags": [101]
            },
            {
                "id": 5,
                "title": "Глубокая очистка данных (Ingestion API)",
                "isCompleted": False,
                "tags": [102] # Assume 102 is 'ingestion'
            }
        ]
        
        # Simple tag filtering for mock
        if tags:
            filtered = [t for t in mock_tasks if any(tag in t["tags"] for tag in tags)]
        else:
            filtered = mock_tasks

        return {
            "success": True,
            "tasks": filtered,
            "hasMore": False
        }
