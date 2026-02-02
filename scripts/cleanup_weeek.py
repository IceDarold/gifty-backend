import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.weeek import WeeekClient

async def cleanup():
    client = WeeekClient()
    print("🧹 Starting Weeek Cleanup...")

    # 1. Projects
    projects_resp = await client.get_projects()
    if not projects_resp.get("success"):
        print(f"❌ Failed to fetch projects: {projects_resp.get('error')}")
        return
    
    projects = projects_resp.get("projects", [])
    for project in projects:
        p_id = project["id"]
        p_name = project["name"]
        print(f"\n📂 Checking Project: {p_name} (ID: {p_id})")
        
        boards_resp = await client.get_boards(p_id)
        if not boards_resp.get("success"):
            print(f"  ❌ Failed to fetch boards: {boards_resp.get('error')}")
            continue
            
        boards = boards_resp.get("boards", [])
        seen_names = {} # name -> id
        
        for board in boards:
            b_id = board["id"]
            b_name = board["name"]
            
            if b_name in seen_names:
                print(f"  🗑️  Duplicate found: '{b_name}' (ID: {b_id}). Original ID: {seen_names[b_name]}")
                # Delete duplicate
                del_resp = await client.delete_board(b_id)
                if del_resp.get("success"):
                    print(f"    ✅ Deleted duplicate board {b_id}")
                else:
                    print(f"    ❌ Failed to delete board {b_id}: {del_resp.get('error')}")
            else:
                seen_names[b_name] = b_id
                print(f"  ℹ️  Board OK: '{b_name}' (ID: {b_id})")

    print("\n✨ Cleanup Complete!")

if __name__ == "__main__":
    asyncio.run(cleanup())
