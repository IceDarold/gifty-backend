import os
import asyncio
import httpx
import json
import logging
from typing import Dict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("weeek_static_fetcher")

# Configuration
WEEEK_API_TOKEN = os.environ.get("WEEEK_API_TOKEN")
WEEEK_WORKSPACE_ID = os.environ.get("WEEEK_WORKSPACE_ID", "911018")
WEEEK_API_BASE = os.environ.get("WEEEK_API_BASE", "https://api.weeek.net/public/v1").rstrip("/")
# Output to the javascripts folder so MkDocs includes it nicely
OUTPUT_FILE = "docs/javascripts/weeek_static_data.js"

class SimpleWeeekClient:
    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    async def get_members(self) -> Dict:
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(f"{WEEEK_API_BASE}/ws/members", headers=self.headers)
                return resp.json() if resp.is_success else {}
            except Exception as e:
                logger.error(f"Error fetching members: {e}")
                return {}

    async def get_board_columns(self, board_id: int) -> Dict:
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(f"{WEEEK_API_BASE}/tm/board-columns", headers=self.headers, params={"boardId": board_id})
                return resp.json() if resp.is_success else {}
            except Exception as e:
                logger.error(f"Error fetching columns for board {board_id}: {e}")
                return {}

    async def get_tags(self) -> Dict:
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(f"{WEEEK_API_BASE}/ws/tags", headers=self.headers)
                return resp.json() if resp.is_success else {}
            except Exception as e:
                logger.error(f"Error fetching tags: {e}")
                return {}

    async def get_all_tasks(self) -> Dict:
        # Request 100 tasks
        params = {"limit": 100} 
        
        async with httpx.AsyncClient() as client:
            try:
                # GET /tm/tasks 
                resp = await client.get(f"{WEEEK_API_BASE}/tm/tasks", headers=self.headers, params=params)
                if not resp.is_success:
                    logger.error(f"Failed to fetch tasks: {resp.status_code} {resp.text}")
                    return {}
                return resp.json()
            except Exception as e:
                logger.error(f"Error fetching tasks: {e}")
                return {}

async def main():
    data = None
    
    if not WEEEK_API_TOKEN:
        logger.warning("WEEEK_API_TOKEN not found. Using empty data.")
        data = None
    else:
        logger.info("Fetching Weeek data...")
        client = SimpleWeeekClient(WEEEK_API_TOKEN)
        
        # 1. Fetch Tasks
        tasks_resp = await client.get_all_tasks()
        tasks = tasks_resp.get("tasks", [])
        logger.info(f"Fetched {len(tasks)} tasks")

        if tasks:
            # 2. Fetch Members (for avatars)
            members_resp = await client.get_members()
            members_map = {}
            if members_resp.get("success"):
                for m in members_resp.get("members", []):
                    members_map[m["id"]] = {
                        "logo": m.get("logo"),
                        "firstName": m.get("firstName"),
                        "lastName": m.get("lastName")
                    }

            # 3. Fetch Columns (for status names)
            unique_board_ids = set(t.get("boardId") for t in tasks if t.get("boardId"))
            columns_map = {}
            
            for bid in unique_board_ids:
                cols_resp = await client.get_board_columns(bid)
                if cols_resp.get("success"):
                    for col in cols_resp.get("boardColumns", []):
                        columns_map[col["id"]] = col["name"]

            # 4. Fetch Tags (for tag filtering by name)
            tags_resp = await client.get_tags()
            all_tags = tags_resp.get("tags", []) if tags_resp.get("success") else []

            data = {
                "success": True,
                "tasks": tasks,
                "workspaceId": WEEEK_WORKSPACE_ID,
                "members": members_map,
                "columns": columns_map,
                "tags": all_tags
            }

    # Ensure directory exists
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    
    # Write as JS variable
    json_str = json.dumps(data, ensure_ascii=False, indent=2) if data else "null"
    js_content = f"window.WEEEK_STATIC_DATA = {json_str};\n"
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(js_content)
    
    logger.info(f"Weeek static data saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
