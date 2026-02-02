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
        for p in products:
            # Generate gift_id if not present or mapping to site_key:url/id
            # For now, let's use site_key:url as a simple unique ID placeholder
            # Real implementation might differ based on provider
            gift_id = f"{p.site_key}:{p.product_url}" 
            
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
        await self.parsing_repo.update_source_stats(source_id, {"processed_items": len(products)})
        
        await self.db.commit()
        return count

    async def ingest_categories(self, categories: List[ScrapedCategory]):
        # Logic for discovery: potentially creating new ParsingSource entries
        # For now, just a placeholder
        pass
