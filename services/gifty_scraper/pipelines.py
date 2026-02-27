from itemadapter import ItemAdapter
import logging
import httpx
import os
import asyncio
import redis.asyncio as aioredis
from datetime import datetime
from typing import List
from gifty_scraper.metrics import scraped_items_total, ingestion_batches_total, ingestion_items_total
from gifty_scraper.items import ProductItem, CategoryItem

def _ts():
    return datetime.utcnow().strftime("%H:%M:%S")


def _as_int_or_none(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            return int(raw)
        except ValueError:
            return None
    return None


def _guess_name_from_url(url: str) -> str:
    cleaned = (url or "").rstrip("/")
    if not cleaned:
        return "category"
    slug = cleaned.split("/")[-1]
    slug = slug.replace("-", " ").replace("_", " ").strip()
    return slug or "category"

class IngestionPipeline:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        core_api_url = os.getenv("CORE_API_URL", "http://api:8000")
        normalized = core_api_url.rstrip("/")
        # Accept both base URL and full ingest endpoint from env.
        if normalized.endswith("/api/v1/internal/ingest-batch"):
            self.api_url = normalized
        elif normalized.endswith("/api/v1/internal"):
            self.api_url = f"{normalized}/ingest-batch"
        else:
            self.api_url = f"{normalized}/api/v1/internal/ingest-batch"
        self.token = os.getenv("INTERNAL_API_TOKEN", "default_internal_token")
        self.batch_size = int(os.getenv("SCRAPY_BATCH_SIZE", "50"))
        self.items_buffer = []
        self.item_count = 0
        self._redis = None

    async def _get_redis(self):
        if self._redis is None:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            try:
                self._redis = aioredis.from_url(redis_url, decode_responses=True)
            except Exception:
                self._redis = None
        return self._redis

    async def _publish(self, source_id, message: str):
        """Publish a log line to Redis so the SSE endpoint can stream it."""
        try:
            r = await self._get_redis()
            if not r:
                return
            channel = f"logs:source:{source_id}"
            buffer_key = f"{channel}:buffer"
            await r.publish(channel, message)
            # Also keep a rolling buffer of last 500 lines for late-joiners
            await r.rpush(buffer_key, message)
            await r.ltrim(buffer_key, -500, -1)
            await r.expire(buffer_key, 3600)  # auto-expire after 1h
        except Exception as e:
            self.logger.debug(f"Redis publish failed (non-critical): {e}")

    async def process_item(self, item, spider):
        self.items_buffer.append(dict(item))
        self.item_count += 1

        item_type = "product" if isinstance(item, ProductItem) else "category"
        scraped_items_total.labels(spider=spider.name, item_type=item_type).inc()

        source_id = getattr(spider, 'source_id', 0)

        # Publish a per-item progress log for products
        if isinstance(item, ProductItem):
            adapter = ItemAdapter(item)
            name = adapter.get("title") or adapter.get("name", "?")
            price = adapter.get("price", "?")
            await self._publish(
                source_id,
                f"[PROGRESS] [{_ts()}] #{self.item_count} scraped: {name} — {price} ₽"
            )
        else:
            adapter = ItemAdapter(item)
            name = adapter.get("name", "?")
            await self._publish(source_id, f"[INFO] [{_ts()}] Category: {name}")

        if len(self.items_buffer) >= self.batch_size:
            self.logger.info(f"Pipeline buffer full ({len(self.items_buffer)}), flushing...")
            await self.flush_items(spider)

        return item

    async def close_spider(self, spider):
        await self.flush_items(spider, is_final=True)
        source_id = getattr(spider, 'source_id', 0)
        await self._publish(source_id, f"[PROGRESS] [{_ts()}] ✅ Spider finished. Total scraped: {self.item_count}")
        if self._redis:
            await self._redis.aclose()

    async def flush_items(self, spider, is_final=False):
        if not self.items_buffer and not is_final:
            return

        batch = list(self.items_buffer)
        self.items_buffer = []

        products = []
        categories = []

        for item in batch:
            if "product_url" in item:
                title = str(item.get("title") or item.get("name") or "").strip()
                product_url = str(item.get("product_url") or "").strip()
                site_key = str(item.get("site_key") or getattr(spider, "site_key", "") or "").strip()
                if not title or not product_url or not site_key:
                    self.logger.debug("Skip invalid product item for ingest: %s", item)
                    continue
                normalized = dict(item)
                normalized["title"] = title
                normalized["product_url"] = product_url
                normalized["site_key"] = site_key
                normalized["source_id"] = _as_int_or_none(item.get("source_id", getattr(spider, "source_id", None)))
                products.append(normalized)
            elif "url" in item:
                url = str(item.get("url") or "").strip()
                site_key = str(item.get("site_key") or getattr(spider, "site_key", "") or "").strip()
                name = str(item.get("name") or item.get("title") or "").strip()
                if not name and url:
                    name = _guess_name_from_url(url)
                if not url or not site_key or not name:
                    self.logger.debug("Skip invalid category item for ingest: %s", item)
                    continue
                normalized = dict(item)
                normalized["url"] = url
                normalized["site_key"] = site_key
                normalized["name"] = name
                categories.append(normalized)

        if not products and not categories:
            return

        first_item = products[0] if products else categories[0]
        source_id = _as_int_or_none(first_item.get("source_id", getattr(spider, 'source_id', None)))
        source_id = source_id if source_id is not None else 0
        run_id = _as_int_or_none(first_item.get("run_id", getattr(spider, 'run_id', None)))
        spider_name = first_item.get("site_key", spider.name)

        payload = {
            "items": products,
            "categories": categories,
            "source_id": source_id,
            "run_id": run_id,
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

                msg = f"[PROGRESS] [{_ts()}] 💾 Batch ingested: {len(products)} products, {len(categories)} categories (total so far: {self.item_count})"
                self.logger.info(f"Successfully ingested {len(products)} products and {len(categories)} categories for {spider_name}")
                await self._publish(source_id, msg)

        except Exception as e:
            ingestion_batches_total.labels(spider=spider_name, status="error").inc()
            details = ""
            if isinstance(e, httpx.HTTPStatusError):
                try:
                    details = e.response.text
                except Exception:
                    details = ""
            extra = f" response={details}" if details else ""
            self.logger.error(f"Failed to ingest batch for {spider_name}: {e}{extra}")
            await self._publish(source_id, f"[ERROR] [{_ts()}] ❌ Batch failed: {e}{extra}")
