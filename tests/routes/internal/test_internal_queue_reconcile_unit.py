from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from routes import internal as internal_routes


class _AllResult:
    def __init__(self, rows):
        self._rows = list(rows)

    def all(self):
        return list(self._rows)


@pytest.mark.anyio
async def test_reconcile_queued_runs_returns_ok_when_no_rows(monkeypatch):
    db = SimpleNamespace(execute=AsyncMock(return_value=_AllResult([])), commit=AsyncMock())
    monkeypatch.setattr(internal_routes, "_fetch_rabbit_queue_stats", AsyncMock(return_value={"status": "ok", "messages_total": 0}), raising=True)

    out = await internal_routes._reconcile_queued_runs_with_rabbit(db)
    assert out["status"] == "ok"
    assert out["stale_runs"] == 0


@pytest.mark.anyio
async def test_reconcile_queued_runs_skips_when_queue_too_large(monkeypatch):
    db = SimpleNamespace(execute=AsyncMock(return_value=_AllResult([(1, 10, datetime(2020, 1, 1, tzinfo=timezone.utc))])), commit=AsyncMock())
    monkeypatch.setattr(internal_routes, "_fetch_rabbit_queue_stats", AsyncMock(return_value={"status": "ok", "messages_total": 2}), raising=True)

    out = await internal_routes._reconcile_queued_runs_with_rabbit(db, max_probe_messages=1)
    assert out["status"] == "skipped"
    assert out["reason"] == "queue_too_large_to_probe"


@pytest.mark.anyio
async def test_reconcile_queued_runs_skips_when_queue_probe_fails(monkeypatch):
    db = SimpleNamespace(execute=AsyncMock(return_value=_AllResult([(1, 10, datetime(2020, 1, 1, tzinfo=timezone.utc))])), commit=AsyncMock())
    monkeypatch.setattr(internal_routes, "_fetch_rabbit_queue_stats", AsyncMock(return_value={"status": "ok", "messages_total": 1}), raising=True)
    monkeypatch.setattr(internal_routes, "_fetch_rabbit_queued_task_ids", AsyncMock(side_effect=RuntimeError("boom")), raising=True)

    out = await internal_routes._reconcile_queued_runs_with_rabbit(db, max_probe_messages=5)
    assert out["status"] == "skipped"
    assert out["reason"] == "queue_probe_failed"


@pytest.mark.anyio
async def test_reconcile_queued_runs_returns_ok_when_all_tasks_present(monkeypatch):
    db = SimpleNamespace(execute=AsyncMock(return_value=_AllResult([(1, 10, datetime(2020, 1, 1, tzinfo=timezone.utc))])), commit=AsyncMock())
    monkeypatch.setattr(internal_routes, "_fetch_rabbit_queue_stats", AsyncMock(return_value={"status": "ok", "messages_total": 1}), raising=True)
    monkeypatch.setattr(internal_routes, "_fetch_rabbit_queued_task_ids", AsyncMock(return_value=({1}, [])), raising=True)

    out = await internal_routes._reconcile_queued_runs_with_rabbit(db, max_probe_messages=5)
    assert out["status"] == "ok"
    assert out["stale_runs"] == 0


class _LockThatSetsLast:
    async def __aenter__(self):
        internal_routes._last_queue_reconcile_at = datetime.now(timezone.utc)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.anyio
async def test_maybe_reconcile_hits_inner_cooldown_branch(monkeypatch):
    internal_routes._last_queue_reconcile_at = None
    monkeypatch.setattr(internal_routes, "_queue_reconcile_lock", _LockThatSetsLast(), raising=True)
    monkeypatch.setattr(internal_routes, "_reconcile_queued_runs_with_rabbit", AsyncMock(return_value={"status": "ok"}), raising=True)

    out = await internal_routes._maybe_reconcile_queued_runs_with_rabbit(SimpleNamespace(), cooldown_seconds=999)
    assert out["status"] == "skipped"
    assert out["reason"] == "cooldown"

