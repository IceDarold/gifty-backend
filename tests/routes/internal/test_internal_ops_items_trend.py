from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.models import ParsingSource
from routes import internal as internal_routes


@dataclass
class _AllResult:
    rows: list

    def all(self):
        return list(self.rows)


@dataclass
class _ScalarOneOrNoneResult:
    value: object

    def scalar_one_or_none(self):
        return self.value


@pytest.mark.anyio
async def test_get_ops_items_trend_cache_hit(fake_db, fake_redis, monkeypatch):
    now = datetime.now(timezone.utc).isoformat()
    cached_payload = {"status": "ok", "items": [], "totals": {}, "granularity": "day", "buckets": 1, "generated_at": now}
    cached = {"payload": cached_payload, "generated_at": now}

    monkeypatch.setattr(internal_routes, "_get_or_create_ops_runtime_state", AsyncMock(return_value=SimpleNamespace()))
    monkeypatch.setattr(
        internal_routes,
        "_serialize_ops_runtime_settings",
        lambda state: {"item": {"ops_snapshot_ttl_ms": 5000, "ops_stale_max_age_ms": 10_000_000, "ops_aggregator_enabled": True}},
    )
    monkeypatch.setattr(internal_routes, "_snapshot_read", AsyncMock(return_value=cached))

    out = await internal_routes.get_ops_items_trend(
        granularity="day", buckets=1, days=None, db=fake_db, redis=fake_redis, force_fresh=False, _="internal"
    )
    assert out["status"] == "ok"
    assert out["stale"] is False
    assert out["snapshot_key"].startswith("ops:snapshot:items_trend:day:1")


@pytest.mark.anyio
async def test_get_ops_items_trend_stale_served_triggers_refresh(fake_db, fake_redis, monkeypatch):
    past = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    cached_payload = {"status": "ok", "items": [], "totals": {}, "granularity": "day", "buckets": 1, "generated_at": past}
    cached = {"payload": cached_payload, "generated_at": past}

    monkeypatch.setattr(internal_routes, "_get_or_create_ops_runtime_state", AsyncMock(return_value=SimpleNamespace()))
    monkeypatch.setattr(
        internal_routes,
        "_serialize_ops_runtime_settings",
        lambda state: {"item": {"ops_snapshot_ttl_ms": 5000, "ops_stale_max_age_ms": 1, "ops_aggregator_enabled": True}},
    )
    monkeypatch.setattr(internal_routes, "_snapshot_read", AsyncMock(return_value=cached))
    refresh = AsyncMock()
    monkeypatch.setattr(internal_routes, "_trigger_snapshot_refresh_if_needed", refresh)

    out = await internal_routes.get_ops_items_trend(
        granularity="day", buckets=1, days=None, db=fake_db, redis=fake_redis, force_fresh=False, _="internal"
    )
    assert out["stale"] is True
    refresh.assert_awaited()


@pytest.mark.anyio
async def test_get_ops_items_trend_force_fresh_writes_snapshot(fake_db, fake_redis, monkeypatch):
    monkeypatch.setattr(internal_routes, "_get_or_create_ops_runtime_state", AsyncMock(return_value=SimpleNamespace()))
    monkeypatch.setattr(
        internal_routes,
        "_serialize_ops_runtime_settings",
        lambda state: {"item": {"ops_snapshot_ttl_ms": 5000, "ops_stale_max_age_ms": 10_000, "ops_aggregator_enabled": False}},
    )
    monkeypatch.setattr(internal_routes, "_compute_ops_items_trend_payload", AsyncMock(return_value={"status": "ok", "items": [], "totals": {}}))
    monkeypatch.setattr(internal_routes, "_snapshot_meta_get", AsyncMock(return_value={}))
    monkeypatch.setattr(internal_routes, "_publish_ops_event", AsyncMock())
    monkeypatch.setattr(internal_routes, "_snapshot_write", AsyncMock(return_value=({"generated_at": None}, True)))

    out = await internal_routes.get_ops_items_trend(
        granularity="day", buckets=1, days=None, db=fake_db, redis=fake_redis, force_fresh=True, _="internal"
    )
    assert out["status"] == "ok"
    assert out["stale"] is False


@pytest.mark.anyio
async def test_compute_ops_items_trend_payload_invalid_granularity(fake_db):
    with pytest.raises(HTTPException) as exc:
        await internal_routes._compute_ops_items_trend_payload(granularity="bad", buckets=1, days=None, db=fake_db)
    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_compute_ops_items_trend_payload_counts_rows(fake_db):
    now = datetime.now(timezone.utc)
    fake_db.execute = AsyncMock(
        side_effect=[
            _AllResult([(now - timedelta(days=1),), (None,), (now,),]),
            _AllResult([(now,),]),
        ]
    )
    out = await internal_routes._compute_ops_items_trend_payload(granularity="day", buckets=2, days=None, db=fake_db)
    assert out["status"] == "ok"
    assert out["totals"]["items_new"] >= 1
    assert out["totals"]["categories_new"] >= 1


@pytest.mark.anyio
async def test_get_ops_source_items_trend_happy_and_errors(fake_db, monkeypatch):
    source = ParsingSource(
        id=1,
        site_key="site",
        url="u",
        type="list",
        is_active=True,
        status="waiting",
        config={"discovery_name": "Cats"},
        created_at=datetime.now(timezone.utc),
        next_sync_at=datetime.now(timezone.utc),
    )

    fake_db.execute = AsyncMock(
        side_effect=[
            _ScalarOneOrNoneResult(None),
        ]
    )
    with pytest.raises(HTTPException) as exc:
        await internal_routes.get_ops_source_items_trend(1, granularity="day", buckets=1, days=None, db=fake_db, _="internal")
    assert exc.value.status_code == 404

    now = datetime.now(timezone.utc)
    fake_db.execute = AsyncMock(
        side_effect=[
            _ScalarOneOrNoneResult(source),
            _AllResult([(now,), (None,),]),
        ]
    )
    out = await internal_routes.get_ops_source_items_trend(1, granularity="day", buckets=1, days=None, db=fake_db, _="internal")
    assert out["status"] == "ok"
    assert out["source_id"] == 1

    fake_db.execute = AsyncMock(side_effect=[_ScalarOneOrNoneResult(source)])
    with pytest.raises(HTTPException) as exc2:
        await internal_routes.get_ops_source_items_trend(1, granularity="bad", buckets=1, days=None, db=fake_db, _="internal")
    assert exc2.value.status_code == 400

