from itemadapter import ItemAdapter
import logging
import httpx
import os
import asyncio
from typing import List
from gifty_scraper.metrics import scraped_items_total, ingestion_batches_total, ingestion_items_total
from gifty_scraper.items import ProductItem, CategoryItem

class IngestionPipeline:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_url = os.getenv("CORE_API_URL", "http://api:8000/internal/ingest-batch")
        self.token = os.getenv("INTERNAL_API_TOKEN", "default_internal_token")
        self.batch_size = int(os.getenv("SCRAPY_BATCH_SIZE", "50"))
        self.items_buffer = []

    async def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        self.items_buffer.append(dict(item))

        # Track scraped items
        item_type = "product" if isinstance(item, ProductItem) else "category"
        scraped_items_total.labels(spider=spider.name, item_type=item_type).inc()

        if len(self.items_buffer) >= self.batch_size:
            await self.flush_items()
            
        return item

    async def close_spider(self, spider):
        # Отправляем остатки при закрытии паука
        await self.flush_items()

    async def flush_items(self):
        if not self.items_buffer:
            return

        batch = list(self.items_buffer)
        self.items_buffer = []
        
        # Берем source_id и site_key из первого элемента
        first_item = batch[0]
        source_id = first_item.get("source_id", 0)
        spider_name = first_item.get("site_key", "unknown")

        payload = {
            "items": batch,
            "source_id": source_id,
            "stats": {"count": len(batch)}
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.api_url, 
                    json=payload,
                    headers={"X-Internal-Token": self.token}
                )
                response.raise_for_status()
                
                ingestion_batches_total.labels(spider=spider_name, status="success").inc()
                ingestion_items_total.labels(spider=spider_name).inc(len(batch))
                
                self.logger.info(f"Successfully ingested batch of {len(batch)} items")
        except Exception as e:
            ingestion_batches_total.labels(spider=spider_name, status="error").inc()
            self.logger.error(f"Failed to ingest batch: {e}")
