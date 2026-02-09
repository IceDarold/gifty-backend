import logging
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.catalog import PostgresCatalogRepository
from app.repositories.parsing import ParsingRepository
from app.schemas.parsing import ScrapedProduct, ScrapedCategory

logger = logging.getLogger(__name__)

class IngestionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.catalog_repo = PostgresCatalogRepository(db)
        self.parsing_repo = ParsingRepository(db)

    async def ingest_products(self, products: List[ScrapedProduct], source_id: int):
        if not products:
            return 0

        # 1. Handle Categories
        external_categories = list(set([p.category for p in products if p.category]))
        if external_categories:
            await self.parsing_repo.get_or_create_category_maps(external_categories)

        # 2. Prepare Product data for Upsert
        product_dicts = []
        seen_gift_ids = set()
        
        for p in products:
            # Generate gift_id if not present or mapping to site_key:url/id
            # For now, let's use site_key:url as a simple unique ID placeholder
            # Real implementation might differ based on provider
            gift_id = f"{p.site_key}:{p.product_url}" 
            
            if gift_id in seen_gift_ids:
                continue
            seen_gift_ids.add(gift_id)
            
            product_dicts.append({
                "gift_id": gift_id,
                "title": p.title,
                "description": p.description,
                "price": p.price,
                "currency": p.currency,
                "image_url": p.image_url,
                "product_url": p.product_url,
                "merchant": p.merchant,
                "category": p.category, # We store raw category for now
                "raw": p.raw_data,
                "is_active": True
            })

        # 3. Bulk Upsert
        count = await self.catalog_repo.upsert_products(product_dicts)
        
        # 4. Update Source Stats (Simplified)
        await self.parsing_repo.update_source_stats(source_id, {
            "processed_items": len(products),
            "new_items": count
        })
        
        # 5. Log Run History
        await self.parsing_repo.log_parsing_run(
            source_id=source_id,
            status="completed",
            items_scraped=len(products),
            items_new=count
        )
        
        await self.db.commit()
        return count

    async def ingest_categories(self, categories: List[ScrapedCategory]):
        if not categories:
            return 0
            
        count = 0
        for cat in categories:
            # We use the category URL as a unique identifier for the ParsingSource
            source_data = {
                "url": cat.url,
                "site_key": cat.site_key,
                "type": "list", # Discovered categories are usually 'list' types
                "strategy": "deep", # They should be parsed thoroughly
                "priority": 50,
                "refresh_interval_hours": 24,
                "is_active": True,
                "status": "waiting",
                "config": {
                    "discovery_name": cat.name,
                    "parent_url": cat.parent_url
                }
            }
            try:
                await self.parsing_repo.upsert_source(source_data)
                count += 1
            except Exception as e:
                logger.error(f"Failed to upsert discovered source {cat.url}: {e}")
        
        await self.db.commit()
        return count
