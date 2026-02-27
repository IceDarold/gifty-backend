import logging
import re
from typing import List, Optional, Set
from datetime import datetime, timedelta
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.catalog import PostgresCatalogRepository
from app.repositories.parsing import ParsingRepository
from app.schemas.parsing import ScrapedProduct, ScrapedCategory

logger = logging.getLogger(__name__)

# Default list of parameters to strip from URLs
DEFAULT_STRIP_PARAMS = {
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
    'yclid', 'gclid', 'fbclid', 'asid', '_openstat'
}

def normalize_url(url: str, strip_params: Optional[Set[str]] = None) -> str:
    """Removes tracking parameters and normalizes the URL."""
    try:
        parsed = urlparse(url)
        params_to_strip = strip_params if strip_params is not None else DEFAULT_STRIP_PARAMS
        
        # Sort query params and filter out tracking ones
        query_params = parse_qsl(parsed.query)
        filtered_params = [
            (k, v) for k, v in query_params 
            if k.lower() not in params_to_strip
        ]
        # Rebuild URL without the noise
        new_query = urlencode(filtered_params)
        normalized = urlunparse(parsed._replace(query=new_query, fragment=""))
        return normalized
    except Exception as e:
        logger.warning(f"Failed to normalize URL {url}: {e}")
        return url

class IngestionService:
    def __init__(self, db: AsyncSession, redis=None):
        self.db = db
        self.catalog_repo = PostgresCatalogRepository(db)
        self.parsing_repo = ParsingRepository(db, redis=redis)

    async def ingest_products(self, products: List[ScrapedProduct], source_id: int, *, run_id: int | None = None):
        if not products:
            return 0

        # Fetch source config for custom normalization
        source = await self.parsing_repo.get_source(source_id)
        strip_params = DEFAULT_STRIP_PARAMS
        if source and source.config:
            custom_strip = source.config.get("strip_params")
            if isinstance(custom_strip, list):
                strip_params = set(custom_strip)

        # 1. Handle Categories
        external_categories = list(set([p.category for p in products if p.category]))
        if external_categories:
            await self.parsing_repo.get_or_create_category_maps(external_categories)

        # 2. Prepare Product data for Upsert
        product_dicts = []
        seen_product_ids = set()

        derived_site_key = None
        if source:
            derived_site_key = str(source.site_key or "").strip() or None

        merchant_name = None
        if derived_site_key:
            merchant = await self.parsing_repo.get_or_create_merchant(derived_site_key)
            merchant_name = merchant.name if merchant else derived_site_key
        
        for p in products:
            site_key = str(p.site_key or "").strip() or derived_site_key
            if not site_key:
                # Cannot construct stable product_id without site_key.
                continue

            clean_url = normalize_url(p.product_url, strip_params=strip_params)
            product_id = f"{site_key}:{clean_url}"
            
            if product_id in seen_product_ids:
                continue
            seen_product_ids.add(product_id)

            if not merchant_name:
                merchant = await self.parsing_repo.get_or_create_merchant(site_key)
                merchant_name = merchant.name if merchant else site_key
            
            product_dicts.append({
                "product_id": product_id,
                "title": p.title,
                "description": p.description,
                "price": p.price,
                "currency": p.currency,
                "image_url": p.image_url,
                "product_url": clean_url,
                "merchant": merchant_name,
                "category": None,
                "raw": p.raw_data,
                "is_active": True,
                "site_key": site_key,
            })

        # 3. Bulk Upsert
        count = await self.catalog_repo.upsert_products(product_dicts)

        # 3.1 Record category links (source is a category/list source).
        if source and source.type == "list" and source.category_id and seen_product_ids:
            await self.parsing_repo.upsert_product_category_links(
                product_ids=seen_product_ids,
                discovered_category_id=int(source.category_id),
                source_id=int(source_id),
                run_id=int(run_id) if run_id else None,
            )
        
        # 4. Update Source Stats
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

    async def ingest_categories(self, categories: List[ScrapedCategory], activation_quota: int = 50):
        """Discovers new ParsingSources. Activates some, puts others in backlog."""
        if not categories:
            return 0
            
        # Count how many we already activated today
        activated_today = await self.parsing_repo.count_discovered_today()
        remaining_quota = max(0, activation_quota - activated_today)

        count = 0
        for i, cat in enumerate(categories):
            clean_url = normalize_url(cat.url)
            
            # If within quota, status is 'waiting', else 'discovered' (backlog)
            # hub (list) sources are activated by default if within quota
            is_within_quota = (i < remaining_quota)
            status = "waiting" if is_within_quota else "discovered"
            is_active = True if is_within_quota else False

            # Check if source already exists
            existing = await self.parsing_repo.get_source_by_url(clean_url)
            if existing:
                continue

            source_data = {
                "url": clean_url,
                "site_key": cat.site_key,
                "type": "list", 
                "strategy": "deep", 
                "priority": 50,
                "refresh_interval_hours": 24,
                "is_active": is_active,
                "status": status,
                "config": {
                    "discovery_name": cat.name,
                    "parent_url": cat.parent_url,
                    "discovered_at": datetime.utcnow().isoformat()
                }
            }
            try:
                await self.parsing_repo.upsert_source(source_data)
                count += 1
            except Exception as e:
                logger.error(f"Failed to upsert discovered source {clean_url}: {e}")
        
        await self.db.commit()
        return count
