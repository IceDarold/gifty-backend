from __future__ import annotations

import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from routes import internal as internal_routes


@pytest.mark.anyio
async def test_stream_ops_events_decodes_bytes_bad_json_and_emits_ping(fake_db, fake_redis, monkeypatch):
    # auth bypass
    monkeypatch.setattr(internal_routes, "verify_internal_token", AsyncMock(return_value="internal"))
    monkeypatch.setattr(internal_routes, "_fetch_rabbit_queue_stats", AsyncMock(return_value={"status": "ok", "messages_total": 1}))

    # prime pubsub with one bad-json bytes message and one valid
    await fake_redis.publish(internal_routes.OPS_EVENTS_CHANNEL, b"{bad-json")
    await fake_redis.publish(
        internal_routes.OPS_EVENTS_CHANNEL,
        json.dumps({"type": "queue.updated", "payload": {"x": 1}}),
    )

    # force ping quickly
    mono = [0.0, 16.0, 16.0]
    monkeypatch.setattr(time, "monotonic", lambda: mono.pop(0) if mono else 16.0)

    resp = await internal_routes.stream_ops_events(db=fake_db, redis=fake_redis, x_internal_token="t", x_tg_init_data=None, tg_init_data=None, internal_token=None)
    it = resp.body_iterator

    first = await it.__anext__()  # initial queue.updated snapshot
    assert "queue.updated" in first

    second = await it.__anext__()
    third = await it.__anext__()
    payloads = [second, third]
    assert any("event: queue.updated" in p for p in payloads)
    assert any("event: ping" in p for p in payloads)
    await it.aclose()


@pytest.mark.anyio
async def test_stream_logs_emits_meta_line_and_ping(fake_db, monkeypatch):
    monkeypatch.setattr(internal_routes, "verify_internal_token", AsyncMock(return_value="internal"))

    line = SimpleNamespace(ts_iso="t", ts_ns=1, labels={"service": "api"}, line="hello")

    async def _tail(*, query: str, limit: int = 200):
        yield line

    loki = SimpleNamespace(tail=_tail)
    monkeypatch.setattr(internal_routes, "LokiLogsClient", lambda: loki, raising=True)

    mono = [0.0, 16.0]
    monkeypatch.setattr(time, "monotonic", lambda: mono.pop(0) if mono else 16.0)

    resp = await internal_routes.stream_logs(db=fake_db, x_internal_token="t", x_tg_init_data=None, tg_init_data=None, internal_token=None, service="api", q=None, limit=1)
    it = resp.body_iterator
    meta = await it.__anext__()
    assert "logs.meta" in meta
    line_ev = await it.__anext__()
    assert "log.line" in line_ev
    ping = await it.__anext__()
    assert "event: ping" in ping
    await it.aclose()
