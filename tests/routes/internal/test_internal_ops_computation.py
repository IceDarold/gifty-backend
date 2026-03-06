from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from routes import internal as internal_routes


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


class _AllResult:
    def __init__(self, rows):
        self._rows = list(rows)

    def all(self):
        return list(self._rows)

    def scalars(self):
        return SimpleNamespace(all=lambda: list(self._rows))


class _RowcountResult:
    def __init__(self, rowcount: int):
        self.rowcount = rowcount


@pytest.mark.asyncio
async def test_reconcile_queued_runs_skips_when_queue_unavailable(monkeypatch):
    db = AsyncMock()
    monkeypatch.setattr(internal_routes, "_fetch_rabbit_queue_stats", AsyncMock(return_value={"status": "error"}), raising=True)
    out = await internal_routes._reconcile_queued_runs_with_rabbit(db)
    assert out["status"] == "skipped"


@pytest.mark.asyncio
async def test_reconcile_queued_runs_marks_stale_and_fixes_sources(monkeypatch):
    # Queue exists but is empty -> all stale queued runs are marked error.
    monkeypatch.setattr(
        internal_routes,
        "_fetch_rabbit_queue_stats",
        AsyncMock(return_value={"status": "ok", "messages_total": 0}),
        raising=True,
    )

    db = AsyncMock()
    db.commit = AsyncMock()
    queued_rows = [
        (1, 10, datetime.now(timezone.utc) - timedelta(minutes=10)),
        (2, 20, datetime.now(timezone.utc) - timedelta(minutes=10)),
    ]
    db.execute = AsyncMock(
        side_effect=[
            _AllResult(queued_rows),  # queued_rows select
            _RowcountResult(2),  # update ParsingRun
            _AllResult([]),  # active_source_rows (none)
            _RowcountResult(2),  # update ParsingSource
        ]
    )

    out = await internal_routes._reconcile_queued_runs_with_rabbit(db, grace_seconds=1)
    assert out["status"] == "ok"
    assert out["stale_runs"] == 2
    assert out["source_status_fixed"] == 2


@pytest.mark.asyncio
async def test_maybe_reconcile_respects_cooldown(monkeypatch):
    db = AsyncMock()
    internal_routes._last_queue_reconcile_at = datetime.now(timezone.utc)
    out = await internal_routes._maybe_reconcile_queued_runs_with_rabbit(db, cooldown_seconds=999)
    assert out["status"] == "skipped"

    internal_routes._last_queue_reconcile_at = None
    monkeypatch.setattr(internal_routes, "_reconcile_queued_runs_with_rabbit", AsyncMock(return_value={"status": "ok"}), raising=True)
    out2 = await internal_routes._maybe_reconcile_queued_runs_with_rabbit(db, cooldown_seconds=0)
    assert out2["status"] == "ok"


@pytest.mark.asyncio
async def test_compute_ops_overview_payload(monkeypatch, fake_redis):
    # Avoid calling full worker discovery logic.
    class _Repo:
        def __init__(self, db, redis=None):
            pass

        async def get_active_workers(self):
            return [{"worker_id": "w", "active_tasks": [1, 2]}]

    monkeypatch.setattr(internal_routes, "ParsingRepository", _Repo, raising=True)
    monkeypatch.setattr(internal_routes, "_maybe_reconcile_queued_runs_with_rabbit", AsyncMock(return_value={"status": "ok"}), raising=True)
    monkeypatch.setattr(internal_routes, "_fetch_rabbit_queue_stats", AsyncMock(return_value={"status": "ok", "messages_total": 3}), raising=True)

    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _AllResult([("completed", 5), ("error", 1)]),  # run status group
            _AllResult([("new", 2), ("rejected", 1)]),  # discovery category counts
            _ScalarResult(100),  # products_total
            _ScalarResult(7),  # products_new_24h
            _ScalarResult(4),  # active_sources
        ]
    )

    out = await internal_routes._compute_ops_overview_payload(db=db, redis=fake_redis)
    assert out["status"] == "ok"
    assert out["runs"]["queued"] == 3
    assert out["runs"]["running"] == 2
    assert out["active_sources"] == 4


@pytest.mark.asyncio
async def test_compute_ops_tasks_trend_payload_parses_snapshots(fake_redis):
    # Put some snapshots (including garbage) into Redis list.
    await fake_redis.lpush(internal_routes.OPS_TASK_SNAPSHOTS_KEY, "not-json")
    await fake_redis.lpush(
        internal_routes.OPS_TASK_SNAPSHOTS_KEY,
        json.dumps(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "queue": 2,
                "running": 1,
                "completed_total": 5,
                "error_total": 1,
            }
        ),
    )
    out = await internal_routes._compute_ops_tasks_trend_payload(granularity="minute", buckets=3, redis=fake_redis)
    assert out["status"] == "ok"
    assert out["buckets"] == 3

    with pytest.raises(Exception):
        await internal_routes._compute_ops_tasks_trend_payload(granularity="bad", buckets=1, redis=fake_redis)


@pytest.mark.asyncio
async def test_compute_ops_scheduler_stats_payload(monkeypatch):
    monkeypatch.setattr(internal_routes, "_get_scheduler_paused_state", AsyncMock(return_value=True), raising=True)

    now = datetime.now(timezone.utc)
    upcoming = [
        SimpleNamespace(
            id=1,
            site_key="site",
            url="u",
            type="list",
            status="waiting",
            priority=10,
            refresh_interval_hours=1,
            next_sync_at=now,
            last_synced_at=now,
        )
    ]

    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _ScalarResult(10),  # active_sources
            _ScalarResult(2),  # paused_sources
            _ScalarResult(3),  # due_now
            _ScalarResult(1),  # overdue_15m
            _ScalarResult(4),  # next_hour_count
            _AllResult([(1, 10)]),  # interval_rows
            _AllResult(upcoming),  # upcoming_rows (scalars().all)
            _AllResult([("completed", 2, 5, 10, 1.5)]),  # run_rows
            _AllResult([SimpleNamespace(date=now.date(), queued_count=1)]),  # queued_history_rows
            _AllResult([SimpleNamespace(date=now.date(), planned_count=2)]),  # planned_future_rows
        ]
    )

    out = await internal_routes._compute_ops_scheduler_stats_payload(db=db)
    assert out["status"] == "ok"
    assert out["summary"]["scheduler_paused"] is True
    assert out["intervals"][0]["sources_count"] == 10
    assert out["upcoming"][0]["site_key"] == "site"

