import asyncio
import logging
import sys
import time
from pathlib import Path

# Add project root to pythonpath
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app.jobs.parsing_scheduler import run_parsing_scheduler
from app.jobs.weeek_reminders import run_weeek_reminders
from app.jobs.ops_aggregator import run_ops_aggregator_tick
from app.db import get_session_context
from app.models import OpsRuntimeState
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("Scheduler")

async def main():
    logger.info("Scheduler service started (Parsing + Reminders).")
    last_reminder_run = None
    last_parsing_run_ts = 0.0
    last_aggregator_run_ts = 0.0
    last_interval_refresh_ts = 0.0
    aggregator_interval_seconds = 2.0
    parsing_interval_seconds = 60

    async def current_aggregator_interval_seconds() -> float:
        try:
            async with get_session_context() as db:
                state = await db.get(OpsRuntimeState, 1)
                if state and int(state.ops_aggregator_interval_ms or 0) > 0:
                    return max(0.5, min(60.0, float(state.ops_aggregator_interval_ms) / 1000.0))
        except Exception:
            pass
        return 2.0

    while True:
        now_ts = time.monotonic()

        # 1. Parsing (minutely)
        if now_ts - last_parsing_run_ts >= parsing_interval_seconds:
            try:
                await run_parsing_scheduler()
            except Exception as e:
                logger.error(f"Error in parsing scheduler loop: {e}")
            finally:
                last_parsing_run_ts = now_ts

        # 2. Ops aggregator (sub-minute, configurable)
        if now_ts - last_interval_refresh_ts >= 2.0:
            aggregator_interval_seconds = await current_aggregator_interval_seconds()
            last_interval_refresh_ts = now_ts
        if now_ts - last_aggregator_run_ts >= aggregator_interval_seconds:
            try:
                await run_ops_aggregator_tick(worker_id="scheduler:main")
            except Exception as e:
                logger.error(f"Error in ops aggregator tick: {e}")
            finally:
                last_aggregator_run_ts = now_ts

        # 3. Weeek Reminders (Hourly)
        try:
            now = datetime.now()
            # Run if we haven't run this hour yet
            if last_reminder_run is None or now.hour != last_reminder_run.hour:
                logger.info("Running Weeek Reminders job...")
                await run_weeek_reminders()
                last_reminder_run = now
        except Exception as e:
            logger.error(f"Error in reminders scheduler loop: {e}")

        # Tick loop
        await asyncio.sleep(0.25)

if __name__ == "__main__":
    asyncio.run(main())
