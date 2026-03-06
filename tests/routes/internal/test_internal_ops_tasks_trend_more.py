from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from routes import internal as internal_routes


@pytest.mark.anyio
async def test_get_ops_tasks_trend_cache_hit(fake_db, fake_redis, monkeypatch):
    now = datetime.now(timezone.utc).isoformat()
    payload = {"status": "ok", "items": [], "totals": {}}
    cached = {"payload": payload, "generated_at": now}

    monkeypatch.setattr(internal_routes, "_get_or_create_ops_runtime_state", AsyncMock(return_value=SimpleNamespace()))
    monkeypatch.setattr(
        internal_routes,
        "_serialize_ops_runtime_settings",
        lambda _: {"item": {"ops_snapshot_ttl_ms": 5000, "ops_stale_max_age_ms": 999999, "ops_aggregator_enabled": True}},
    )
    monkeypatch.setattr(internal_routes, "_snapshot_read", AsyncMock(return_value=cached))

    out = await internal_routes.get_ops_tasks_trend(granularity="day", buckets=2, force_fresh=False, db=fake_db, redis=fake_redis, _="internal")
    assert out["status"] == "ok"
    assert out["stale"] is False


@pytest.mark.anyio
async def test_get_ops_tasks_trend_stale_served_triggers_refresh(fake_db, fake_redis, monkeypatch):
    past = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    payload = {"status": "ok", "items": [], "totals": {}}
    cached = {"payload": payload, "generated_at": past}

    monkeypatch.setattr(internal_routes, "_get_or_create_ops_runtime_state", AsyncMock(return_value=SimpleNamespace()))
    monkeypatch.setattr(
        internal_routes,
        "_serialize_ops_runtime_settings",
        lambda _: {"item": {"ops_snapshot_ttl_ms": 5000, "ops_stale_max_age_ms": 1, "ops_aggregator_enabled": True}},
    )
    monkeypatch.setattr(internal_routes, "_snapshot_read", AsyncMock(return_value=cached))
    refresh = AsyncMock()
    monkeypatch.setattr(internal_routes, "_trigger_snapshot_refresh_if_needed", refresh)

    out = await internal_routes.get_ops_tasks_trend(granularity="day", buckets=2, force_fresh=False, db=fake_db, redis=fake_redis, _="internal")
    assert out["stale"] is True
    refresh.assert_awaited()


@pytest.mark.anyio
async def test_get_ops_tasks_trend_cache_miss_write_changed_publishes(fake_db, fake_redis, monkeypatch):
    monkeypatch.setattr(internal_routes, "_get_or_create_ops_runtime_state", AsyncMock(return_value=SimpleNamespace()))
    monkeypatch.setattr(
        internal_routes,
        "_serialize_ops_runtime_settings",
        lambda _: {"item": {"ops_snapshot_ttl_ms": 5000, "ops_stale_max_age_ms": 10, "ops_aggregator_enabled": False}},
    )
    monkeypatch.setattr(internal_routes, "_snapshot_read", AsyncMock(return_value=None))
    monkeypatch.setattr(internal_routes, "_compute_ops_tasks_trend_payload", AsyncMock(return_value={"status": "ok", "items": [], "totals": {}}))
    monkeypatch.setattr(internal_routes, "_snapshot_write", AsyncMock(return_value=({"generated_at": "t"}, True)))
    monkeypatch.setattr(internal_routes, "_snapshot_meta_get", AsyncMock(return_value={"x": {"version": 1}}))

    pub = AsyncMock()
    monkeypatch.setattr(internal_routes, "_publish_ops_event", pub)

    out = await internal_routes.get_ops_tasks_trend(granularity="day", buckets=2, force_fresh=False, db=fake_db, redis=fake_redis, _="internal")
    assert out["status"] == "ok"
    pub.assert_awaited()


@pytest.mark.anyio
async def test_get_ops_tasks_trend_force_fresh_redis_write_error_degraded(fake_db, fake_redis, monkeypatch):
    monkeypatch.setattr(internal_routes, "_get_or_create_ops_runtime_state", AsyncMock(return_value=SimpleNamespace()))
    monkeypatch.setattr(
        internal_routes,
        "_serialize_ops_runtime_settings",
        lambda _: {"item": {"ops_snapshot_ttl_ms": 5000, "ops_stale_max_age_ms": 10, "ops_aggregator_enabled": False}},
    )
    monkeypatch.setattr(internal_routes, "_compute_ops_tasks_trend_payload", AsyncMock(return_value={"status": "ok", "items": [], "totals": {}}))
    monkeypatch.setattr(internal_routes, "_snapshot_write", AsyncMock(side_effect=RuntimeError("redis down")))

    out = await internal_routes.get_ops_tasks_trend(granularity="day", buckets=2, force_fresh=True, db=fake_db, redis=fake_redis, _="internal")
    assert out["status"] == "ok"

