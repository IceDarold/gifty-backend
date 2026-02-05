import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.weeek import WeeekClient

async def setup():
    client = WeeekClient()
    print("🚀 Starting Weeek Provisioning...")

    # 1. Projects (Already exist: 2 - Backend, 3 - Frontend)
    backend_id = 2
    
    # 2. Create Tags
    tags_to_create = [
        {"title": "Parsing", "color": "blue"},
        {"title": "Ingestion", "color": "green"},
        {"title": "AI", "color": "purple"},
        {"title": "Auth", "color": "orange"},
        {"title": "Infrastructure", "color": "red"}
    ]
    
    print("🏷️  Creating Tags...")
    existing_tags_resp = await client.get_tags()
    existing_tags = existing_tags_resp.get("tags", []) if existing_tags_resp.get("success") else []
    
    tag_map = {t["title"].lower(): t["id"] for t in existing_tags}
    
    for tag_def in tags_to_create:
        name = tag_def["title"]
        if name.lower() not in tag_map:
            resp = await client.create_tag(name, tag_def["color"])
            if resp.get("success"):
                tag_map[name.lower()] = resp["tag"]["id"]
                print(f"✅ Created tag: {name}")
            else:
                print(f"❌ Failed to create tag {name}: {resp.get('error')}")
        else:
            print(f"ℹ️  Tag already exists: {name}")

    # 3. Create Boards
    boards_to_create = [
        "Infrastructure & DevOps",
        "Parsing & Ingestion",
        "AI & Recommendations",
        "Auth & Settings"
    ]
    
    print("\n📋 Creating Boards...")
    # Pass projectId to get_boards to see boards in the Backend project
    existing_boards_resp = await client.get_boards(backend_id)
    existing_boards = existing_boards_resp.get("boards", []) if existing_boards_resp.get("success") else []
    
    board_map = {b["name"].lower(): b["id"] for b in existing_boards}
    
    for board_name in boards_to_create:
        if board_name.lower() not in board_map:
            resp = await client.create_board({"name": board_name, "projectId": backend_id})
            if resp.get("success"):
                board_map[board_name.lower()] = resp["board"]["id"]
                print(f"✅ Created board: {board_name}")
            else:
                print(f"❌ Failed to create board {board_name}: {resp.get('error')}")
        else:
            print(f"ℹ️  Board already exists: {board_name}")

    # Map human names to IDs for task creation
    board_id_map = {}
    for name in boards_to_create:
         board_id_map[name] = board_map.get(name.lower())

    # 4. Create Tasks
    tasks = [
        # Infrastructure
        {"title": "Setup RabbitMQ Cluster", "board": "Infrastructure & DevOps", "tag": "Infrastructure", "complete": True},
        {"title": "Dockerize all services", "board": "Infrastructure & DevOps", "tag": "Infrastructure", "complete": True},
        {"title": "Implement CI/CD pipeline", "board": "Infrastructure & DevOps", "tag": "Infrastructure", "complete": False},
        
        # Parsing
        {"title": "Base Scrapy Spider Class", "board": "Parsing & Ingestion", "tag": "Parsing", "complete": True},
        {"title": "Proxy Rotation Middleware", "board": "Parsing & Ingestion", "tag": "Parsing", "complete": False},
        {"title": "Adaptive Scheduling Logic", "board": "Parsing & Ingestion", "tag": "Parsing", "complete": False},
        
        # Ingestion
        {"title": "Ingestion API Endpoint", "board": "Parsing & Ingestion", "tag": "Ingestion", "complete": True},
        {"title": "Data Validation Schemas", "board": "Parsing & Ingestion", "tag": "Ingestion", "complete": True},
        
        # AI
        {"title": "Gemini Category Classifier", "board": "AI & Recommendations", "tag": "AI", "complete": True},
        {"title": "LLM Giftability Scoring", "board": "AI & Recommendations", "tag": "AI", "complete": False},
        
        # Auth
        {"title": "Google OAuth Integration", "board": "Auth & Settings", "tag": "Auth", "complete": True},
        {"title": "JWT Token Management", "board": "Auth & Settings", "tag": "Auth", "complete": True}
    ]

    print("\n🏗️  Populating Tasks...")
    for t in tasks:
        b_id = board_id_map.get(t["board"])
        tag_id = tag_map.get(t["tag"].lower())
        
        if not b_id:
            print(f"⚠️  Skipping task '{t['title']}' - board not found.")
            continue
            
        task_data = {
            "title": t["title"],
            "projectId": backend_id,
            "boardId": b_id,
            "tags": [tag_id] if tag_id else []
        }
        
        resp = await client.create_task(task_data)
        if resp.get("success"):
            task_id = resp["task"]["id"]
            print(f"✅ Created task: {t['title']}")
            
            # Update with tags as POST might not support them
            if tag_id:
                await client.update_task(task_id, {"tags": [tag_id]})
                print(f"🏷️  Assigned tag to: {t['title']}")
                
            if t["complete"]:
                await client.complete_task(task_id)
                print(f"✔️  Marked as completed: {t['title']}")
        else:
            print(f"❌ Failed to create task {t['title']}: {resp.get('error')}")

    print("\n✨ Provisioning Complete!")

if __name__ == "__main__":
    asyncio.run(setup())
