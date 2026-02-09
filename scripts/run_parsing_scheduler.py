import asyncio
import logging
import sys
import time
from pathlib import Path

# Add project root to pythonpath
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app.jobs.parsing_scheduler import run_parsing_scheduler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ParsingScheduler")

async def main():
    logger.info("Parsing scheduler service started.")
    while True:
        try:
            await run_parsing_scheduler()
        except Exception as e:
            logger.error(f"Error in parsing scheduler loop: {e}")
        
        # Check every 1 minute
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
