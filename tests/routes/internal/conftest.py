from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
import queue
from typing import Any, Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock

from routes import internal as internal_routes


@dataclass
class _ValueWithExpiry:
    value: Any
    expires_at: Optional[float]


class FakePubSub:
    def __init__(self, redis: "FakeRedis"):
        self._redis = redis
        self._channels: set[str] = set()

    async def subscribe(self, *channels: str) -> None:
        for ch in channels:
            self._channels.add(ch)
            self._redis._ensure_channel(ch)

    async def unsubscribe(self, *channels: str) -> None:
        for ch in channels:
            self._channels.discard(ch)

    async def close(self) -> None:
        self._channels.clear()

    async def get_message(self, *, ignore_subscribe_messages: bool = True, timeout: float = 0.0) -> Optional[dict]:
        # We only emulate message delivery for one channel (the tests use a single channel).
        if not self._channels:
            if timeout:
                await asyncio.sleep(min(timeout, 0.01))
            return None

        channel = next(iter(self._channels))
        q = self._redis._channels[channel]
        try:
            data = await asyncio.to_thread(q.get, True, timeout if timeout else 0.01)
        except queue.Empty:
            return None
        return {"type": "message", "channel": channel, "data": data}


class FakeRedis:
    def __init__(self):
        self._kv: dict[str, _ValueWithExpiry] = {}
        self._lists: dict[str, list[Any]] = {}
        self._channels: dict[str, queue.Queue] = {}

    def _now(self) -> float:
        return time.time()

    def _ensure_channel(self, channel: str) -> None:
        if channel not in self._channels:
            self._channels[channel] = queue.Queue()

    def _is_expired(self, item: _ValueWithExpiry) -> bool:
        return item.expires_at is not None and item.expires_at <= self._now()

    async def get(self, key: str):
        item = self._kv.get(key)
        if item is None:
            return None
        if self._is_expired(item):
            self._kv.pop(key, None)
            return None
        return item.value

    async def set(self, key: str, value: Any, ex: int | None = None, px: int | None = None, nx: bool = False):
        if nx and key in self._kv and not self._is_expired(self._kv[key]):
            return False
        ttl = None
        if px is not None:
            ttl = px / 1000.0
        elif ex is not None:
            ttl = float(ex)
        expires_at = (self._now() + ttl) if ttl is not None else None
        self._kv[key] = _ValueWithExpiry(value=value, expires_at=expires_at)
        return True

    async def setex(self, key: str, ttl: int, value: Any):
        return await self.set(key, value, ex=int(ttl))

    async def delete(self, *keys: str):
        deleted = 0
        for key in keys:
            if key in self._kv:
                deleted += 1
                self._kv.pop(key, None)
            if key in self._lists:
                deleted += 1
                self._lists.pop(key, None)
        return deleted

    async def lpush(self, key: str, value: Any):
        self._lists.setdefault(key, [])
        self._lists[key].insert(0, value)
        return len(self._lists[key])

    async def ltrim(self, key: str, start: int, end: int):
        values = self._lists.get(key, [])
        self._lists[key] = values[start : end + 1]
        return True

    async def lrange(self, key: str, start: int, end: int):
        values = self._lists.get(key, [])
        if end == -1:
            end = len(values) - 1
        return values[start : end + 1]

    async def publish(self, channel: str, message: Any):
        self._ensure_channel(channel)
        self._channels[channel].put(message)
        return 1

    def pubsub(self):
        return FakePubSub(self)

    async def scan(self, cursor: int = 0, match: str | None = None, count: int = 100):
        # Minimal implementation: we don't support keyspace scans in unit tests.
        return 0, []

    async def ping(self):
        return True

    async def info(self, section: str | None = None):
        return {"used_memory": 0}


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def fake_db():
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.get = AsyncMock(return_value=None)
    return db


@pytest.fixture
def internal_app(fake_db, fake_redis):
    app = FastAPI()
    app.include_router(internal_routes.router)

    async def override_get_db():
        yield fake_db

    async def override_get_redis():
        return fake_redis

    app.dependency_overrides[internal_routes.get_db] = override_get_db
    app.dependency_overrides[internal_routes.get_redis] = override_get_redis
    app.dependency_overrides[internal_routes.verify_internal_token] = lambda: "internal"
    return app


@pytest.fixture
def client(internal_app) -> TestClient:
    return TestClient(internal_app)


@pytest.fixture(autouse=True)
def _patch_external_calls(monkeypatch):
    # Avoid touching RabbitMQ/real external services from internal routes tests.
    monkeypatch.setattr(
        internal_routes,
        "get_notification_service",
        lambda: AsyncMock(notify=AsyncMock(return_value=True)),
        raising=True,
    )
    return None


def assert_ok(resp):
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("status") == "ok"
    return body
