from __future__ import annotations

import logging
from typing import Optional

from app.db import get_session_context
from app.repositories.catalog import PostgresCatalogRepository
from app.services.embeddings import EmbeddingService
from app.core.logic_config import logic_config

logger = logging.getLogger(__name__)


async def process_embeddings_job(
    batch_size: int = 32,
    limit_total: Optional[int] = None,
    model_name: Optional[str] = None,
    model_version: str = "1.0",
) -> None:
    """
    Job to find products without embeddings (or outdated hash) and generate them.
    """
    actual_model = model_name or logic_config.model_embedding
    logger.info(f"Starting embeddings job. Model: {actual_model} (v{model_version})")
    
    # Initialize service (loads model)
    embedding_service = EmbeddingService(model_name=actual_model)
    
    total_processed = 0
    
    while True:
        # Check if we hit the total limit for this run
        if limit_total and total_processed >= limit_total:
            logger.info(f"Hit total limit of {limit_total}. Stopping.")
            break

        async with get_session_context() as session:
            repo = PostgresCatalogRepository(session)
            
            # 1. Fetch batch of products needing embeddings
            products = await repo.get_products_without_embeddings(
                model_version=model_version, 
                limit=batch_size
            )
            
            if not products:
                logger.info("No more products to embed.")
                break
            
            # 2. Extract texts
            texts = [p.content_text or "" for p in products]
            
            # 3. Generate embeddings
            try:
                vectors = await embedding_service.embed_batch_async(texts)
            except Exception as e:
                logger.error(f"Failed to embed batch: {e}", exc_info=True)
                break
            
            # 4. Prepare data for save
            embeddings_data = []
            for product, vector in zip(products, vectors):
                embeddings_data.append({
                    "gift_id": product.gift_id,
                    "model_name": actual_model,
                    "model_version": model_version,
                    "dim": len(vector),
                    "embedding": vector,
                    "content_hash": product.content_hash,
                })
            
            # 5. Save to DB
            saved_count = await repo.save_embeddings(embeddings_data)
            await session.commit()
            
            total_processed += saved_count
            logger.info(f"Processed batch of {saved_count} products. Total: {total_processed}")

    logger.info(f"Embeddings job finished. Total processed: {total_processed}")
