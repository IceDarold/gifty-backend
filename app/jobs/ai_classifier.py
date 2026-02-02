import logging
from typing import List
from app.db import get_session_context
from app.repositories.parsing import ParsingRepository
from app.models import CategoryMap
from sqlalchemy import select

logger = logging.getLogger(__name__)

from app.services.intelligence import IntelligenceService

async def classify_new_categories():
    """
    Job for AI classification using external service.
    1. Fetch categories from CategoryMap with NULL internal_category_id.
    2. Use IntelligenceService to map them to internal categories.
    3. Update CategoryMap.
    """
    logger.info("Starting AI category classification via External API...")
    
    intelligence = IntelligenceService()
    
    async with get_session_context() as session:
        # 1. Fetch unmapped categories
        stmt = select(CategoryMap).where(CategoryMap.internal_category_id.is_(None)).limit(50)
        result = await session.execute(stmt)
        unmapped_categories = result.scalars().all()
        
        if not unmapped_categories:
            logger.info("No unmapped categories found.")
            return

        external_names = [c.external_name for c in unmapped_categories]
        
        # 2. Get list of all internal categories (Mock list for now, 
        # normally fetched from a categories table)
        # TODO: Replace with real internal categories fetch
        internal_categories = [
            {"id": 1, "name": "Электроника и гаджеты"},
            {"id": 2, "name": "Дом и интерьер"},
            {"id": 3, "name": "Кухня"},
            {"id": 4, "name": "Хобби и творчество"},
            {"id": 5, "name": "Одежда и аксессуары"},
            {"id": 6, "name": "Игрушки и развлечения"}
        ]

        # 3. Request classification from Gifty Intelligence
        mappings = await intelligence.classify_categories(
            external_names=external_names,
            internal_categories=internal_categories
        )

        # 4. Apply mappings
        mapping_dict = {m["external_name"]: m["internal_category_id"] for m in mappings}
        
        for category in unmapped_categories:
            new_id = mapping_dict.get(category.external_name)
            if new_id:
                category.internal_category_id = new_id
                logger.info(f"Classified: {category.external_name} -> {new_id}")

        await session.commit()
    
    logger.info("AI category classification completed.")
