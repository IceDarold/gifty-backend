import logging
from app.db import get_session_context
from app.repositories.parsing import ParsingRepository
from app.utils.rabbitmq import publish_parsing_task
from sqlalchemy import select
from app.models import OpsRuntimeState

logger = logging.getLogger(__name__)


async def _is_scheduler_paused() -> bool:
    try:
        async with get_session_context() as session:
            paused = (
                await session.execute(
                    select(OpsRuntimeState.scheduler_paused).where(OpsRuntimeState.id == 1)
                )
            ).scalar_one_or_none()
            return bool(paused) if paused is not None else False
    except Exception:
        logger.exception("Failed to read persistent scheduler pause state; fallback to running")
        return False

async def run_parsing_scheduler():
    logger.info("Starting parsing scheduler loop...")

    if await _is_scheduler_paused():
        logger.info("Parsing scheduler is paused. Skipping this cycle.")
        return
    
    async with get_session_context() as session:
        repo = ParsingRepository(session)
        
        # 1. Get sources that need syncing
        sources = await repo.get_due_sources(limit=20)
        
        if not sources:
            logger.info("No sources due for syncing.")
            return
            
        logger.info(f"Found {len(sources)} sources to sync.")
        
        for source in sources:
            run = await repo.create_parsing_run(source_id=source.id, status="queued")
            task = {
                "source_id": source.id,
                "run_id": run.id,
                "url": source.url,
                "site_key": source.site_key,
                "type": source.type,
                "strategy": source.strategy,
                "config": source.config
            }
            
            # 2. Publish to RabbitMQ
            success = publish_parsing_task(task)
            
            if success:
                # Update status and next_sync_at to prevent re-scheduling
                await repo.set_queued(source.id)
            else:
                logger.error(f"Failed to queue task for source {source.id}")
                await repo.update_parsing_run(
                    run.id,
                    status="error",
                    error_message="Failed to publish task to RabbitMQ in scheduler",
                )

        await session.commit()
    
    logger.info("Parsing scheduler loop completed.")

async def activate_discovered_sources():
    """Activates sources from 'discovered' backlog using daily quota."""
    logger.info("Starting backlog activation job...")
    
    async with get_session_context() as session:
        repo = ParsingRepository(session)
        
        # 1. Check how many activated today
        activated_today = await repo.count_discovered_today()
        # Daily limit (can be moved to settings later)
        daily_limit = 200 
        
        remaining = max(0, daily_limit - activated_today)
        if remaining <= 0:
            logger.info("Daily activation quota reached.")
            return

        # 2. Get sources from backlog
        backlog = await repo.get_discovered_sources(limit=remaining)
        if not backlog:
            logger.info("Backlog is empty.")
            return
            
        logger.info(f"Activating {len(backlog)} sources from backlog.")
        await repo.activate_sources([s.id for s in backlog])
        
    logger.info("Backlog activation completed.")
