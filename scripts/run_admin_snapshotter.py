import asyncio
import logging
import sys
import time
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app.config import get_settings
from app.jobs.admin_snapshotter import run_admin_snapshotter_loop_split, run_admin_snapshotter_tick

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("AdminSnapshotter")


async def main() -> None:
    await run_admin_snapshotter_tick()
    await run_admin_snapshotter_loop_split()


if __name__ == "__main__":
    asyncio.run(main())
