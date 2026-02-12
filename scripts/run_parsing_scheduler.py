import asyncio
import logging
import sys
from pathlib import Path

# Add project root to pythonpath
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app.jobs.parsing_scheduler import run_parsing_scheduler
from app.jobs.weeek_reminders import run_weeek_reminders
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("Scheduler")

async def main():
    logger.info("Scheduler service started (Parsing + Reminders).")
    last_reminder_run = None
    
    while True:
        # 1. Parsing
        try:
            await run_parsing_scheduler()
        except Exception as e:
            logger.error(f"Error in parsing scheduler loop: {e}")
        
        # 2. Weeek Reminders (Hourly)
        try:
            now = datetime.now()
            # Run if we haven't run this hour yet
            if last_reminder_run is None or now.hour != last_reminder_run.hour:
                logger.info("Running Weeek Reminders job...")
                await run_weeek_reminders()
                last_reminder_run = now
        except Exception as e:
            logger.error(f"Error in reminders scheduler loop: {e}")

        # Check every 1 minute
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
