from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from routes import internal as internal_routes


@dataclass
class _LogLine:
    ts_iso: str
    ts_ns: int
    labels: dict
    line: str


@pytest.mark.anyio
async def test_list_log_services_success_and_fallback(monkeypatch, fake_db):
    client = SimpleNamespace(label_values=AsyncMock(return_value=["api", "api", "scraper"]))
    monkeypatch.setattr(internal_routes, "LokiLogsClient", lambda: client)

    out = await internal_routes.list_log_services(db=fake_db, _="internal")
    assert out["items"] == ["api", "scraper"]

    client2 = SimpleNamespace(label_values=AsyncMock(side_effect=RuntimeError("boom")))
    monkeypatch.setattr(internal_routes, "LokiLogsClient", lambda: client2)
    out2 = await internal_routes.list_log_services(db=fake_db, _="internal")
    assert "api" in out2["items"]


@pytest.mark.anyio
async def test_query_logs_success_and_error(monkeypatch, fake_db):
    lines = [
        _LogLine(ts_iso="t", ts_ns=1, labels={"service": "api", "container": "c"}, line="hello"),
    ]
    client = SimpleNamespace(query_range=AsyncMock(return_value=lines))
    monkeypatch.setattr(internal_routes, "LokiLogsClient", lambda: client)
    monkeypatch.setattr(internal_routes, "build_logql_query", lambda service, contains: "{x}")

    out = await internal_routes.query_logs(service="api", q="h", limit=10, since_seconds=10, db=fake_db, _="internal")
    assert out["items"][0]["line"] == "hello"
    assert out["query"] == "{x}"

    client2 = SimpleNamespace(query_range=AsyncMock(side_effect=RuntimeError("boom")))
    monkeypatch.setattr(internal_routes, "LokiLogsClient", lambda: client2)
    with pytest.raises(HTTPException) as exc:
        await internal_routes.query_logs(service="api", q="h", limit=10, since_seconds=10, db=fake_db, _="internal")
    assert exc.value.status_code == 502


@pytest.mark.anyio
async def test_get_system_health_db_and_redis_paths(fake_db, fake_redis):
    fake_db.execute = AsyncMock(return_value=True)
    fake_redis.ping = AsyncMock(return_value=True)
    fake_redis.info = AsyncMock(return_value={"used_memory_human": "1MB"})

    out = await internal_routes.get_system_health(db=fake_db, redis=fake_redis, _="internal")
    assert out["database"]["status"] == "Connected"
    assert out["redis"]["status"] == "Healthy"

    fake_db.execute = AsyncMock(side_effect=RuntimeError("boom"))
    fake_redis.ping = AsyncMock(side_effect=RuntimeError("boom"))
    out2 = await internal_routes.get_system_health(db=fake_db, redis=fake_redis, _="internal")
    assert out2["database"]["status"] == "ERROR"
    assert out2["redis"]["status"] == "ERROR"


class _TinyPubSub:
    def __init__(self, messages: list[dict]):
        self._messages = list(messages)
        self.subscribed = []
        self.unsubscribed = []
        self.closed = False

    async def subscribe(self, channel: str):
        self.subscribed.append(channel)

    async def unsubscribe(self, channel: str):
        self.unsubscribed.append(channel)

    async def close(self):
        self.closed = True

    async def get_message(self, *, ignore_subscribe_messages: bool = True, timeout: float = 0.0):
        await asyncio.sleep(0)
        return self._messages.pop(0) if self._messages else None


@pytest.mark.anyio
async def test_get_source_log_stream_sends_buffer_and_messages(monkeypatch):
    pubsub = _TinyPubSub(
        messages=[
            {"type": "message", "data": b"m1"},
            None,
        ]
    )

    redis = SimpleNamespace(
        lrange=AsyncMock(return_value=[b"b1", "b2"]),
        pubsub=lambda: pubsub,
    )

    resp = await internal_routes.get_source_log_stream(1, redis=redis)
    agen = resp.body_iterator

    first = await agen.__anext__()
    second = await agen.__anext__()
    third = await agen.__anext__()
    fourth = await agen.__anext__()
    assert "b1" in first
    assert "b2" in second
    assert "m1" in third
    assert ":ping" in fourth
    await agen.aclose()

