from __future__ import annotations

import os
import threading
import time
from typing import Any, Optional


def _get_env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    raw = raw.strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


class TTLCache:
    def __init__(self, ttl_seconds: int, max_items: int = 5000) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_items = max_items
        self._lock = threading.Lock()
        self._items: dict[str, tuple[Any, float, float]] = {}

    def get(self, key: str) -> Optional[Any]:
        now = time.time()
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            value, expires_at, _created_at = item
            if expires_at <= now:
                self._items.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        now = time.time()
        expires_at = now + self.ttl_seconds
        with self._lock:
            self._prune_expired(now)
            self._items[key] = (value, expires_at, now)
            if len(self._items) > self.max_items:
                self._evict_oldest()

    def _prune_expired(self, now: float) -> None:
        expired = [k for k, (_, expires_at, _) in self._items.items() if expires_at <= now]
        for key in expired:
            self._items.pop(key, None)

    def _evict_oldest(self) -> None:
        if not self._items:
            return
        to_remove = len(self._items) - self.max_items
        if to_remove <= 0:
            return
        ordered = sorted(self._items.items(), key=lambda item: item[1][2])
        for key, _ in ordered[:to_remove]:
            self._items.pop(key, None)


def default_cache() -> TTLCache:
    ttl_seconds = _get_env_int("RECO_CACHE_TTL_SECONDS", 3600)
    max_items = _get_env_int("RECO_CACHE_MAX_ITEMS", 5000)
    return TTLCache(ttl_seconds=ttl_seconds, max_items=max_items)
