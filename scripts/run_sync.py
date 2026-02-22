import asyncio
import logging
import sys
from pathlib import Path

# Add project root to pythonpath
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app.jobs.catalog_sync import catalog_sync_full
from app.config import get_settings

logging.basicConfig(level=logging.INFO)

async def main():
    print("Starting manual catalog sync...")
    settings = get_settings()
    # Ensure source_id is set
    source_id = settings.takprodam_source_id
    if not source_id:
        print("Error: TAKPRODAM_SOURCE_ID not set in env")
        return

    result = await catalog_sync_full(source_id=source_id)
    print("Sync finished:", result)

if __name__ == "__main__":
    asyncio.run(main())
