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
        # print(f"DEBUG_PIPELINE: Item received for {spider.name}, buffer size: {len(self.items_buffer)}")

        # Track scraped items
        item_type = "product" if isinstance(item, ProductItem) else "category"
        scraped_items_total.labels(spider=spider.name, item_type=item_type).inc()

        if len(self.items_buffer) >= self.batch_size:
            self.logger.info(f"Pipeline buffer full ({len(self.items_buffer)}), flushing...")
            await self.flush_items(spider)
            
        return item

    async def close_spider(self, spider):
        # Отправляем остатки при закрытии паука
        await self.flush_items(spider)

    async def flush_items(self, spider):
        if not self.items_buffer:
            return

        batch = list(self.items_buffer)
        self.items_buffer = []
        
        products = []
        categories = []
        
        for item in batch:
            # Check what kind of item it is. 
            if "product_url" in item:
                products.append(item)
            elif "url" in item and "name" in item:
                categories.append(item)

        if not products and not categories:
            return

        # Use site_key from first available item or spider name
        first_item = products[0] if products else categories[0]
        source_id = first_item.get("source_id", spider.source_id if hasattr(spider, 'source_id') else 0)
        spider_name = first_item.get("site_key", spider.name)

        payload = {
            "items": products,
            "categories": categories,
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
                
                self.logger.info(f"Successfully ingested {len(products)} products and {len(categories)} categories for {spider_name}")
        except Exception as e:
            ingestion_batches_total.labels(spider=spider_name, status="error").inc()
            self.logger.error(f"Failed to ingest batch for {spider_name}: {e}")
