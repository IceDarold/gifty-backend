from __future__ import annotations

import json
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from routes import internal as internal_routes


@dataclass
class _Resp:
    status_code: int = 200
    _json: object = None

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("http error")

    def json(self):
        return self._json


class _ClientCM:
    def __init__(self, *, get_resp=None, post_resp=None, raise_on_enter: Exception | None = None):
        self._get_resp = get_resp
        self._post_resp = post_resp
        self._raise_on_enter = raise_on_enter
        self.get = AsyncMock(return_value=get_resp)
        self.post = AsyncMock(return_value=post_resp)

    async def __aenter__(self):
        if self._raise_on_enter:
            raise self._raise_on_enter
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None


@pytest.mark.anyio
async def test_fetch_rabbit_queue_stats_non_200_and_exception(monkeypatch):
    monkeypatch.setattr("httpx.AsyncClient", lambda timeout=5.0: _ClientCM(get_resp=_Resp(status_code=500, _json={})))
    out = await internal_routes._fetch_rabbit_queue_stats()
    assert out["status"] == "error"

    monkeypatch.setattr("httpx.AsyncClient", lambda timeout=5.0: _ClientCM(raise_on_enter=RuntimeError("boom")))
    out2 = await internal_routes._fetch_rabbit_queue_stats()
    assert out2["status"] == "error"


@pytest.mark.anyio
async def test_fetch_rabbit_queued_tasks_parses_payloads(monkeypatch):
    msgs = [
        {"payload": json.dumps({"run_id": 1, "source_id": 2})},
        {"payload": {"run_id": 3}},
        {"payload": 123},
        {"payload": "{bad-json"},
    ]
    monkeypatch.setattr("httpx.AsyncClient", lambda timeout=8.0: _ClientCM(post_resp=_Resp(status_code=200, _json=msgs)))
    tasks = await internal_routes._fetch_rabbit_queued_tasks(limit=10)
    assert {"run_id": 1, "source_id": 2} in tasks
    assert {"run_id": 3} in tasks


@pytest.mark.anyio
async def test_fetch_rabbit_queued_task_ids_extracts_ints(monkeypatch):
    monkeypatch.setattr(
        internal_routes,
        "_fetch_rabbit_queued_tasks",
        AsyncMock(return_value=[{"run_id": 1, "source_id": 2}, {"run_id": "x"}, {"source_id": None}]),
    )
    run_ids, source_ids = await internal_routes._fetch_rabbit_queued_task_ids(limit=5)
    assert run_ids == {1}
    assert source_ids == {2}


@pytest.mark.anyio
async def test_publish_ops_event_handles_none_and_redis_fail(fake_redis, monkeypatch):
    await internal_routes._publish_ops_event(None, "x", {"a": 1})

    async def _boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(fake_redis, "publish", _boom)
    await internal_routes._publish_ops_event(fake_redis, "x", {"a": 1})


@pytest.mark.anyio
async def test_get_ops_overview_cache_miss_writes_and_publishes(fake_db, fake_redis, monkeypatch):
    cache_key = internal_routes._snapshot_key("overview")

    monkeypatch.setattr(internal_routes, "_get_or_create_ops_runtime_state", AsyncMock(return_value=SimpleNamespace()))
    monkeypatch.setattr(
        internal_routes,
        "_serialize_ops_runtime_settings",
        lambda _: {"item": {"ops_snapshot_ttl_ms": 5000, "ops_stale_max_age_ms": 10, "ops_aggregator_enabled": False}},
    )
    monkeypatch.setattr(internal_routes, "_snapshot_read", AsyncMock(return_value=None))
    monkeypatch.setattr(internal_routes, "_compute_ops_overview_payload", AsyncMock(return_value={"status": "ok"}))
    monkeypatch.setattr(internal_routes, "_snapshot_write", AsyncMock(return_value=({"generated_at": "t"}, True)))
    monkeypatch.setattr(internal_routes, "_snapshot_meta_get", AsyncMock(return_value={cache_key: {"version": 5}}))

    pub = AsyncMock()
    monkeypatch.setattr(internal_routes, "_publish_ops_event", pub)

    out = await internal_routes.get_ops_overview(db=fake_db, redis=fake_redis, force_fresh=False, _="internal")
    assert out["status"] == "ok"
    pub.assert_awaited()


@pytest.mark.anyio
async def test_get_ops_overview_force_fresh_redis_write_error_degraded(fake_db, fake_redis, monkeypatch):
    monkeypatch.setattr(internal_routes, "_get_or_create_ops_runtime_state", AsyncMock(return_value=SimpleNamespace()))
    monkeypatch.setattr(
        internal_routes,
        "_serialize_ops_runtime_settings",
        lambda _: {"item": {"ops_snapshot_ttl_ms": 5000, "ops_stale_max_age_ms": 10, "ops_aggregator_enabled": False}},
    )
    monkeypatch.setattr(internal_routes, "_compute_ops_overview_payload", AsyncMock(return_value={"status": "ok"}))
    monkeypatch.setattr(internal_routes, "_snapshot_write", AsyncMock(side_effect=RuntimeError("redis down")))

    out = await internal_routes.get_ops_overview(db=fake_db, redis=fake_redis, force_fresh=True, _="internal")
    assert out["status"] == "ok"


@pytest.mark.anyio
async def test_scheduler_paused_state_helpers(fake_db):
    fake_db.execute = AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None))
    assert await internal_routes._get_scheduler_paused_state(fake_db) is False

    fake_db.execute = AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: True))
    assert await internal_routes._get_scheduler_paused_state(fake_db) is True
