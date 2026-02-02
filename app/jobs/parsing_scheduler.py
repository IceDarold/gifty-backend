import logging
from app.db import get_session_context
from app.repositories.parsing import ParsingRepository
from app.utils.rabbitmq import publish_parsing_task

logger = logging.getLogger(__name__)

async def run_parsing_scheduler():
    logger.info("Starting parsing scheduler loop...")
    
    async with get_session_context() as session:
        repo = ParsingRepository(session)
        
        # 1. Get sources that need syncing
        sources = await repo.get_due_sources(limit=20)
        
        if not sources:
            logger.info("No sources due for syncing.")
            return
            
        logger.info(f"Found {len(sources)} sources to sync.")
        
        for source in sources:
            task = {
                "source_id": source.id,
                "url": source.url,
                "site_key": source.site_key,
                "type": source.type,
                "strategy": source.strategy,
                "config": source.config
            }
            
            # 2. Publish to RabbitMQ
            success = publish_parsing_task(task)
            
            if success:
                # Update next_sync_at to prevent re-scheduling immediately
                # In a real app, this should be more robust
                # (e.g. status='queued')
                await repo.update_source_stats(source.id, {"status": "queued"})
            else:
                logger.error(f"Failed to queue task for source {source.id}")

        await session.commit()
    
    logger.info("Parsing scheduler loop completed.")
