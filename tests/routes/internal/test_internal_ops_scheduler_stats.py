from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from routes import internal as internal_routes


@dataclass
class _ScalarResult:
    value: object

    def scalar(self):
        return self.value


@dataclass
class _ScalarOneOrNoneResult:
    value: object

    def scalar_one_or_none(self):
        return self.value


@dataclass
class _AllResult:
    rows: list

    def all(self):
        return list(self.rows)


@dataclass
class _ScalarsAllResult:
    items: list

    def scalars(self):
        return SimpleNamespace(all=lambda: list(self.items))


@pytest.mark.anyio
async def test_get_ops_scheduler_stats_cache_hit(fake_db, fake_redis, monkeypatch):
    now = datetime.now(timezone.utc).isoformat()
    payload = {"status": "ok", "summary": {"x": 1}}
    cached = {"payload": payload, "generated_at": now}

    monkeypatch.setattr(internal_routes, "_get_or_create_ops_runtime_state", AsyncMock(return_value=SimpleNamespace()))
    monkeypatch.setattr(
        internal_routes,
        "_serialize_ops_runtime_settings",
        lambda _: {"item": {"ops_snapshot_ttl_ms": 5000, "ops_stale_max_age_ms": 999999, "ops_aggregator_enabled": True}},
    )
    monkeypatch.setattr(internal_routes, "_snapshot_read", AsyncMock(return_value=cached))

    out = await internal_routes.get_ops_scheduler_stats(db=fake_db, redis=fake_redis, force_fresh=False, _="internal")
    assert out["status"] == "ok"
    assert out["stale"] is False


@pytest.mark.anyio
async def test_get_ops_scheduler_stats_stale_served_triggers_refresh(fake_db, fake_redis, monkeypatch):
    past = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    cached = {"payload": {"status": "ok"}, "generated_at": past}

    monkeypatch.setattr(internal_routes, "_get_or_create_ops_runtime_state", AsyncMock(return_value=SimpleNamespace()))
    monkeypatch.setattr(
        internal_routes,
        "_serialize_ops_runtime_settings",
        lambda _: {"item": {"ops_snapshot_ttl_ms": 5000, "ops_stale_max_age_ms": 1, "ops_aggregator_enabled": True}},
    )
    monkeypatch.setattr(internal_routes, "_snapshot_read", AsyncMock(return_value=cached))
    refresh = AsyncMock()
    monkeypatch.setattr(internal_routes, "_trigger_snapshot_refresh_if_needed", refresh)

    out = await internal_routes.get_ops_scheduler_stats(db=fake_db, redis=fake_redis, force_fresh=False, _="internal")
    assert out["status"] == "ok"
    assert out["stale"] is True
    refresh.assert_awaited()


@pytest.mark.anyio
async def test_get_ops_scheduler_stats_force_fresh_redis_write_failure_degraded(fake_db, fake_redis, monkeypatch):
    monkeypatch.setattr(internal_routes, "_get_or_create_ops_runtime_state", AsyncMock(return_value=SimpleNamespace()))
    monkeypatch.setattr(
        internal_routes,
        "_serialize_ops_runtime_settings",
        lambda _: {"item": {"ops_snapshot_ttl_ms": 5000, "ops_stale_max_age_ms": 10, "ops_aggregator_enabled": False}},
    )
    monkeypatch.setattr(internal_routes, "_compute_ops_scheduler_stats_payload", AsyncMock(return_value={"status": "ok", "summary": {}}))
    monkeypatch.setattr(internal_routes, "_snapshot_write", AsyncMock(side_effect=RuntimeError("redis down")))

    out = await internal_routes.get_ops_scheduler_stats(db=fake_db, redis=fake_redis, force_fresh=True, _="internal")
    assert out["status"] == "ok"
    assert out["stale"] is False


@pytest.mark.anyio
async def test_compute_ops_scheduler_stats_payload_smoke(fake_db, monkeypatch):
    monkeypatch.setattr(internal_routes, "_get_scheduler_paused_state", AsyncMock(return_value=True))

    now = datetime.now(timezone.utc)
    upcoming = [
        SimpleNamespace(
            id=10,
            site_key="s",
            url="u",
            type="list",
            status="waiting",
            priority=5,
            refresh_interval_hours=24,
            next_sync_at=now + timedelta(minutes=5),
            last_synced_at=now - timedelta(hours=1),
        )
    ]
    run_rows = [("completed", 2, 3, 4, 1.5)]
    queued_history_rows = [SimpleNamespace(date=(now - timedelta(days=1)).date(), queued_count=3)]
    planned_future_rows = [SimpleNamespace(date=(now + timedelta(days=1)).date(), planned_count=7)]

    fake_db.execute = AsyncMock(
        side_effect=[
            _ScalarResult(5),  # active_sources
            _ScalarResult(1),  # paused_sources
            _ScalarResult(2),  # due_now
            _ScalarResult(1),  # overdue_15m
            _ScalarResult(4),  # next hour
            _AllResult([(24, 10)]),  # interval_rows
            _ScalarsAllResult(upcoming),  # upcoming
            _AllResult(run_rows),  # runs by status
            _AllResult(queued_history_rows),  # queued history
            _AllResult(planned_future_rows),  # planned future
        ]
    )

    out = await internal_routes._compute_ops_scheduler_stats_payload(db=fake_db)
    assert out["status"] == "ok"
    assert out["summary"]["scheduler_paused"] is True
    assert out["intervals"][0]["refresh_interval_hours"] == 24
    assert out["upcoming"][0]["source_id"] == 10
    assert out["runs_24h"]["completed"]["count"] == 2
