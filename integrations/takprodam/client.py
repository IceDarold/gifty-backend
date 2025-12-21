from __future__ import annotations

import logging
import os
import time
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


class TakprodamClient:
    def __init__(
        self,
        api_base: Optional[str] = None,
        api_token: Optional[str] = None,
        source_id: Optional[int] = None,
        timeout_s: float = 8.0,
        max_retries: int = 3,
    ) -> None:
        self.api_base = (api_base or os.getenv("TAKPRODAM_API_BASE") or "").strip()
        self.api_token = (api_token or os.getenv("TAKPRODAM_API_TOKEN") or "").strip()
        self.source_id = source_id or self._parse_int(os.getenv("TAKPRODAM_SOURCE_ID"))
        self.timeout_s = timeout_s
        self.max_retries = max_retries

    @staticmethod
    def _parse_int(value: Optional[str]) -> Optional[int]:
        if value is None:
            return None
        value = value.strip()
        return int(value) if value.isdigit() else None

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_token}",
        }

    def _request(self, path: str, params: dict[str, Any]) -> Optional[dict[str, Any] | list[Any]]:
        if not self.api_base or not self.api_token:
            logger.error("Takprodam config missing: base or token is empty")
            return None

        url = f"{self.api_base.rstrip('/')}/{path.lstrip('/')}"

        for attempt in range(1, self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout_s) as client:
                    response = client.get(url, headers=self._headers(), params=params)
                if response.status_code >= 400:
                    logger.warning(
                        "Takprodam error %s: %s",
                        response.status_code,
                        response.text,
                    )
                    return None
                return response.json()
            except (httpx.RequestError, httpx.TimeoutException) as exc:
                logger.warning("Takprodam request failed (attempt %s/%s): %s", attempt, self.max_retries, exc)
                if attempt < self.max_retries:
                    time.sleep(0.5 * (2 ** (attempt - 1)))

        return None

    def search_products(
        self,
        query: str,
        limit: int = 50,
        offset: int = 0,
        source_id: int | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "q": query,
            "limit": limit,
            "offset": offset,
            "source_id": source_id or self.source_id,
        }

        data = self._request("product/", params=params)
        if data is None:
            return []

        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]

        if isinstance(data, dict):
            items = data.get("items") or data.get("results") or []
            return [item for item in items if isinstance(item, dict)]

        logger.warning("Takprodam response has unexpected format")
        return []
