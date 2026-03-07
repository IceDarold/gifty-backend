from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from routes import internal as internal_routes


@dataclass
class _AllResult:
    rows: list

    def all(self):
        return list(self.rows)


@dataclass
class _ScalarResult:
    value: int

    def scalar(self):
        return self.value


@pytest.mark.anyio
async def test_get_ops_overview_cache_hit(fake_db, fake_redis, monkeypatch):
    now = datetime.now(timezone.utc).isoformat()
    payload = {"status": "ok", "ts": now}
    cached = {"payload": payload, "generated_at": now}

    monkeypatch.setattr(internal_routes, "_get_or_create_ops_runtime_state", AsyncMock(return_value=SimpleNamespace()))
    monkeypatch.setattr(
        internal_routes,
        "_serialize_ops_runtime_settings",
        lambda _: {"item": {"ops_snapshot_ttl_ms": 5000, "ops_stale_max_age_ms": 999999, "ops_aggregator_enabled": True}},
    )
    monkeypatch.setattr(internal_routes, "_snapshot_read", AsyncMock(return_value=cached))

    out = await internal_routes.get_ops_overview(db=fake_db, redis=fake_redis, force_fresh=False, _="internal")
    assert out["status"] == "ok"
    assert out["stale"] is False


@pytest.mark.anyio
async def test_get_ops_overview_stale_served_triggers_refresh(fake_db, fake_redis, monkeypatch):
    past = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    payload = {"status": "ok", "ts": past}
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

    out = await internal_routes.get_ops_overview(db=fake_db, redis=fake_redis, force_fresh=False, _="internal")
    assert out["stale"] is True
    refresh.assert_awaited()


@pytest.mark.anyio
async def test_compute_ops_overview_payload_smoke(fake_db, fake_redis, monkeypatch):
    monkeypatch.setattr(internal_routes, "_maybe_reconcile_queued_runs_with_rabbit", AsyncMock())
    monkeypatch.setattr(internal_routes, "_fetch_rabbit_queue_stats", AsyncMock(return_value={"status": "ok", "messages_total": 3}))
    monkeypatch.setattr(internal_routes, "_append_ops_task_snapshot", AsyncMock())

    repo = SimpleNamespace(get_active_workers=AsyncMock(return_value=[{"active_tasks": [{"id": 1}]}]))
    monkeypatch.setattr(internal_routes, "ParsingRepository", lambda db, redis=None: repo)

    fake_db.execute = AsyncMock(
        side_effect=[
            _AllResult([("completed", 2), ("error", 1)]),
            _AllResult([("promoted", 5)]),
            _ScalarResult(100),
            _ScalarResult(7),
            _ScalarResult(9),
        ]
    )

    out = await internal_routes._compute_ops_overview_payload(db=fake_db, redis=fake_redis)
    assert out["status"] == "ok"
    assert out["runs"]["queued"] == 3
    assert out["runs"]["running"] == 1


@pytest.mark.anyio
async def test_compute_ops_tasks_trend_payload_aggregates_snapshots(fake_redis):
    key = internal_routes.OPS_TASK_SNAPSHOTS_KEY
    now = datetime.now(timezone.utc)
    older = (now - timedelta(days=3)).isoformat()
    recent = (now - timedelta(hours=2)).isoformat()
    await fake_redis.lpush(
        key,
        json.dumps({"ts": older, "queue": 1, "running": 0, "completed_total": 10, "error_total": 1}),
    )
    await fake_redis.lpush(
        key,
        json.dumps({"ts": recent, "queue": 2, "running": 1, "completed_total": 12, "error_total": 2}),
    )
    await fake_redis.lpush(key, "{bad-json")

    out = await internal_routes._compute_ops_tasks_trend_payload(granularity="day", buckets=2, redis=fake_redis)
    assert out["status"] == "ok"
    assert out["totals"]["queue_max"] >= 1
    assert out["totals"]["running_max"] >= 0


@pytest.mark.anyio
async def test_compute_ops_tasks_trend_payload_week_and_ts_edge_cases(fake_redis):
    key = internal_routes.OPS_TASK_SNAPSHOTS_KEY
    # bad ts type should be skipped; naive iso should get tzinfo attached
    await fake_redis.lpush(key, json.dumps({"ts": 123, "queue": 1, "running": 0, "completed_total": 1, "error_total": 0}))
    await fake_redis.lpush(key, json.dumps({"ts": "2025-01-01T00:00:00", "queue": 2, "running": 1, "completed_total": 3, "error_total": 1}))

    out = await internal_routes._compute_ops_tasks_trend_payload(granularity="week", buckets=2, redis=fake_redis)
    assert out["status"] == "ok"
    assert out["granularity"] == "week"

    out2 = await internal_routes._compute_ops_tasks_trend_payload(granularity="hour", buckets=2, redis=fake_redis)
    assert out2["status"] == "ok"
    assert out2["granularity"] == "hour"


@pytest.mark.anyio
async def test_ops_scheduler_pause_resume_redis_failures_do_not_block(fake_db, fake_redis, monkeypatch):
    monkeypatch.setattr(internal_routes, "_set_scheduler_paused_state", AsyncMock())

    async def _boom(*a, **k):
        raise RuntimeError("redis down")

    monkeypatch.setattr(fake_redis, "set", _boom)
    out = await internal_routes.pause_ops_scheduler(db=fake_db, redis=fake_redis, _="internal")
    assert out["paused"] is True

    monkeypatch.setattr(fake_redis, "delete", _boom)
    out2 = await internal_routes.resume_ops_scheduler(db=fake_db, redis=fake_redis, _="internal")
    assert out2["paused"] is False


@pytest.mark.anyio
async def test_get_ops_tasks_trend_force_fresh_writes_snapshot(fake_db, fake_redis, monkeypatch):
    monkeypatch.setattr(internal_routes, "_get_or_create_ops_runtime_state", AsyncMock(return_value=SimpleNamespace()))
    monkeypatch.setattr(
        internal_routes,
        "_serialize_ops_runtime_settings",
        lambda _: {"item": {"ops_snapshot_ttl_ms": 5000, "ops_stale_max_age_ms": 10, "ops_aggregator_enabled": False}},
    )
    monkeypatch.setattr(internal_routes, "_compute_ops_tasks_trend_payload", AsyncMock(return_value={"status": "ok", "items": [], "totals": {}}))
    monkeypatch.setattr(internal_routes, "_snapshot_write", AsyncMock(return_value=({"generated_at": None}, False)))

    out = await internal_routes.get_ops_tasks_trend(
        granularity="day", buckets=1, force_fresh=True, db=fake_db, redis=fake_redis, _="internal"
    )
    assert out["status"] == "ok"
