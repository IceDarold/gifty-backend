from itemadapter import ItemAdapter
import logging
import httpx
import os
import asyncio
from typing import List

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
        
        # Берем source_id из первого элемента (они обычно одинаковые для одного запуска)
        source_id = batch[0].get("source_id", 0)

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
                self.logger.info(f"Successfully ingested batch of {len(batch)} items")
        except Exception as e:
            self.logger.error(f"Failed to ingest batch: {e}")
