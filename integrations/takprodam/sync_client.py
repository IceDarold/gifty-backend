from __future__ import annotations

import logging
from collections.abc import Generator
from typing import Any

from integrations.takprodam.client import TakprodamClient

logger = logging.getLogger(__name__)


class TakprodamSyncClient(TakprodamClient):
    """Client extended for catalog synchronization."""

    def get_products_page(
        self,
        page: int = 1,
        limit: int = 1000,
        source_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch a single page of products."""
        params = {
            "page": page,
            "limit": limit,
            "source_id": source_id or self.source_id,
        }
        # Based on user info: https://api.takprodam.ru/v2/publisher/product/
        # Client._request prepends base url.
        # Ensure 'product/' is correct path. Existing client uses 'product/'
        data = self._request("product/", params=params)
        
        if not data:
            return []

        # Takprodam response format normalization
        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            # Standard pagination response usually keys: items, results, data
            items = data.get("items") or data.get("results") or data.get("data") or []
        
        return [item for item in items if isinstance(item, dict)]

    def iter_all_products(
        self,
        batch_size: int = 1000,
        max_pages: int | None = None,
    ) -> Generator[list[dict[str, Any]], None, None]:
        """Yields batches of products."""
        page = 1
        while True:
            if max_pages and page > max_pages:
                break
                
            logger.info("Fetching Takprodam page %s (limit=%s)", page, batch_size)
            items = self.get_products_page(page=page, limit=batch_size)
            
            if not items:
                break
                
            yield items
            
            if len(items) < batch_size:
                # Last page
                break
                
            page += 1
