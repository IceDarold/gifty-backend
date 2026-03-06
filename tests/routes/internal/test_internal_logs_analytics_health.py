from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.loki_logs import LokiLogLine
from routes import internal as internal_routes


def test_logs_services_success_and_fallback(client, monkeypatch):
    class _Client:
        async def label_values(self, label: str):
            assert label == "service"
            return ["api", "api", "redis"]

    monkeypatch.setattr(internal_routes, "LokiLogsClient", lambda: _Client(), raising=True)
    resp = client.get("/api/v1/internal/logs/services")
    assert resp.status_code == 200
    assert resp.json()["items"] == ["api", "redis"]

    class _Fail:
        async def label_values(self, label: str):
            raise RuntimeError("down")

    monkeypatch.setattr(internal_routes, "LokiLogsClient", lambda: _Fail(), raising=True)
    resp2 = client.get("/api/v1/internal/logs/services")
    assert resp2.status_code == 200
    assert "postgres" in resp2.json()["items"]


def test_logs_query_success_and_error(client, monkeypatch):
    class _Client:
        async def query_range(self, **kwargs):
            return [
                LokiLogLine(ts_ns=1, line="x", labels={"service": "api", "container": "c"}),
            ]

    monkeypatch.setattr(internal_routes, "LokiLogsClient", lambda: _Client(), raising=True)
    resp = client.get("/api/v1/internal/logs/query", params={"service": "api", "q": "err", "limit": 1, "since_seconds": 5})
    assert resp.status_code == 200
    assert resp.json()["items"][0]["line"] == "x"

    class _Fail:
        async def query_range(self, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr(internal_routes, "LokiLogsClient", lambda: _Fail(), raising=True)
    bad = client.get("/api/v1/internal/logs/query", params={"since_seconds": 5})
    assert bad.status_code == 502


@pytest.mark.asyncio
async def test_logs_stream_generator_emits_meta_and_lines_and_error(monkeypatch, fake_db):
    # stream_logs calls verify_internal_token directly, not as a dependency.
    monkeypatch.setattr(internal_routes, "verify_internal_token", AsyncMock(return_value="internal"), raising=True)

    class _Client:
        async def tail(self, **kwargs):
            yield LokiLogLine(ts_ns=1, line="hello", labels={"service": "api"})
            raise RuntimeError("down")

    monkeypatch.setattr(internal_routes, "LokiLogsClient", lambda: _Client(), raising=True)
    resp = await internal_routes.stream_logs(db=fake_db, x_internal_token="t", service="api", q=None, limit=1)
    assert resp.media_type == "text/event-stream"

    chunks = []
    async for chunk in resp.body_iterator:
        chunks.append(chunk)
        if len(chunks) >= 3:
            break
    await resp.body_iterator.aclose()

    text = "".join(chunks)
    assert "event: logs.meta" in text
    assert "event: log.line" in text
    assert "event: logs.error" in text


def test_internal_intelligence_and_llm_analytics(fake_db, client):
    # get_intelligence_stats does 3 db.execute calls and uses res.one()/res.all()
    metrics = SimpleNamespace(total_requests=2, total_cost=0.1, total_tokens=10, avg_latency=12.0)
    fake_db.execute = AsyncMock(
        side_effect=[
            SimpleNamespace(one=lambda: metrics),
            SimpleNamespace(all=lambda: [SimpleNamespace(provider="p", count=2, cost=0.1)]),
            SimpleNamespace(all=lambda: [SimpleNamespace(hour=1, avg_latency=15.0)]),
            # get_llm_logs: total scalar_one + rows scalars().all
            SimpleNamespace(scalar_one=lambda: 1),
            SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [SimpleNamespace(id="i", created_at=datetime.now(timezone.utc), provider="p", model="m", call_type="t", status="ok", error_type=None, error_message=None, provider_request_id=None, prompt_hash=None, params={}, latency_ms=1, prompt_tokens=1, completion_tokens=1, total_tokens=2, cost_usd=0.01, session_id=None, experiment_id=None, variant_id=None)])),
            # throughput points
            SimpleNamespace(all=lambda: [SimpleNamespace(ts=datetime(2025, 1, 1, tzinfo=timezone.utc), count=3)]),
            # breakdown items
            SimpleNamespace(all=lambda: [SimpleNamespace(key="p", requests=1, cost=0.1, tokens=10, avg_latency_ms=1.0)]),
        ]
    )

    resp = client.get("/api/v1/internal/analytics/intelligence", params={"days": 7})
    assert resp.status_code == 200, resp.text
    assert resp.json()["metrics"]["total_requests"] == 2

    logs = client.get("/api/v1/internal/analytics/llm/logs", params={"days": 7, "limit": 1})
    assert logs.status_code == 200
    assert logs.json()["total"] == 1

    thr = client.get("/api/v1/internal/analytics/llm/throughput", params={"days": 7, "bucket": "hour"})
    assert thr.status_code == 200
    assert thr.json()["points"][0]["count"] == 3

    br = client.get("/api/v1/internal/analytics/llm/breakdown", params={"days": 7, "group_by": "provider"})
    assert br.status_code == 200
    assert br.json()["items"][0]["key"] == "p"


def test_internal_health_ok_and_degraded(fake_db, fake_redis, client):
    # ok path
    fake_db.execute = AsyncMock(return_value=True)
    resp = client.get("/api/v1/internal/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["database"]["status"] == "Connected"
    assert body["redis"]["status"] == "Healthy"

    # degraded: db and redis failures are swallowed
    async def _raise(*args, **kwargs):
        raise RuntimeError("down")

    fake_db.execute = AsyncMock(side_effect=_raise)
    fake_redis.ping = AsyncMock(side_effect=_raise)
    resp2 = client.get("/api/v1/internal/health")
    assert resp2.status_code == 200
    assert resp2.json()["database"]["status"] == "ERROR"
    assert resp2.json()["redis"]["status"] == "ERROR"
