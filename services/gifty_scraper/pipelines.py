# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter


import logging
import httpx
import os

class IngestionPipeline:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_url = os.getenv("CORE_API_URL", "http://api:8000/internal/ingest-batch")
        self.token = os.getenv("INTERNAL_API_TOKEN", "default_internal_token")

    async def process_item(self, item, spider):
        # In a real implementation, we would batch items
        # For now, let's keep it simple
        self.logger.debug(f"Ingesting item: {item.get('title')}")
        
        # We need to wrap it in IngestBatchRequest format
        # This is a simplified per-item ingestion (slow, for demo)
        payload = {
            "items": [dict(item)],
            "source_id": item.get("source_id", 0),
            "stats": {}
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.api_url, 
                    json=payload,
                    headers={"X-Internal-Token": self.token}
                )
                response.raise_for_status()
        except Exception as e:
            self.logger.error(f"Failed to ingest item: {e}")
            
        return item
