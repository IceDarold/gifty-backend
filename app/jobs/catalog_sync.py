from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session_context
from app.repositories.catalog import PostgresCatalogRepository
from integrations.takprodam.sync_client import TakprodamSyncClient
from app.utils.catalog import build_content_text, build_content_hash

logger = logging.getLogger(__name__)


def _normalize_product(item: dict) -> dict:
    """Convert Takprodam item to local Product model usage."""
    # Mapping based on the actual Takprodam response provided by the user
    product_id = f"takprodam:{item['id']}"
    content_text = build_content_text(item)
    image_url = item.get("image_url")
    
    return {
        "product_id": product_id,
        "site_key": "takprodam",
        "title": item.get("title") or "Untitled",
        "description": item.get("description"),
        "price": float(item["price"]) if item.get("price") else None,
        "currency": item.get("currency", "RUB"),
        "image_url": image_url,
        "product_url": item.get("tracking_link") or item.get("external_link") or "",
        "merchant": item.get("store_title"),
        "category": item.get("product_category"),
        "raw": item,
        "is_active": True,
        "content_text": content_text,
        "content_hash": build_content_hash(content_text, image_url),
    }


async def catalog_sync_full(source_id: int | None = None) -> dict[str, Any]:
    """
    Full catalog synchronization job.
    1. Iterates all pages from Takprodam.
    2. Upserts products to DB.
    3. Handles identifying inactive products (soft delete logic marks others as is_active=False).
    """
    settings = get_settings()
    client = TakprodamSyncClient(
        source_id=source_id or settings.takprodam_source_id,
        api_base=settings.takprodam_api_base,
        api_token=settings.takprodam_api_token,
    )
    total_synced = 0
    pages_count = 0
    
    # We collect all IDs seen in this run to mark others as inactive later.
    seen_ids = set()

    async with get_session_context() as session:
        repo = PostgresCatalogRepository(session)
        
        for batch in client.iter_all_products():
            normalized_batch = []
            for item in batch:
                if not item.get("id"):
                    continue
                product = _normalize_product(item)
                normalized_batch.append(product)
                seen_ids.add(product["product_id"])
            
            if normalized_batch:
                count = await repo.upsert_products(normalized_batch)
                total_synced += count
                await session.commit()
            
            pages_count += 1
            if pages_count % 10 == 0:
                logger.info("Synced %d pages, %d products...", pages_count, total_synced)

        # Soft-delete logic
        if seen_ids:
            logger.info("Marking inactive products (soft-delete)...")
            deactivated_count = await repo.mark_inactive_except(seen_ids)
            await session.commit()
            logger.info("Deactivated %d products.", deactivated_count)
        
        final_count = await repo.get_active_products_count()
        logger.info("Sync complete. Total synced: %d. Active in DB: %d", total_synced, final_count)
    
    return {
        "synced_count": total_synced,
        "pages_processed": pages_count,
        "deactivated_count": deactivated_count if seen_ids else 0,
        "status": "success"
    }
