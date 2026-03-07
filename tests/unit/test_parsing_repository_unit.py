from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.repositories.parsing import ParsingRepository


class _Result:
    def __init__(self, *, scalars=None, all_rows=None, one=None, scalar=None, scalar_one_or_none=None, rowcount=None):
        self._scalars = scalars
        self._all_rows = all_rows
        self._one = one
        self._scalar = scalar
        self._scalar_one_or_none = scalar_one_or_none
        self.rowcount = rowcount

    def scalars(self):
        return SimpleNamespace(all=lambda: list(self._scalars or []))

    def all(self):
        return list(self._all_rows or [])

    def one(self):
        return self._one

    def one_or_none(self):
        return self._one

    def scalar(self):
        return self._scalar

    def scalar_one_or_none(self):
        return self._scalar_one_or_none


@pytest.mark.asyncio
async def test_upsert_source_validates_url():
    repo = ParsingRepository(AsyncMock())
    with pytest.raises(ValueError):
        await repo.upsert_source({"site_key": "s"})


@pytest.mark.asyncio
async def test_upsert_source_creates_and_updates(monkeypatch):
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = lambda obj: None

    repo = ParsingRepository(session)

    # Create new
    session.execute = AsyncMock(side_effect=[_Result(scalar_one_or_none=None)])
    created = await repo.upsert_source({"url": "u", "site_key": "s", "type": "hub", "strategy": "discovery", "is_active": False, "status": "waiting", "refresh_interval_hours": 1, "priority": 1})
    assert created.url == "u"

    # Update existing
    existing = SimpleNamespace(url="u", site_key="s", status="waiting")
    session.execute = AsyncMock(side_effect=[_Result(scalar_one_or_none=existing)])
    updated = await repo.upsert_source({"url": "u", "status": "running"})
    assert updated.status == "running"


@pytest.mark.asyncio
async def test_report_source_error_retry_and_broken():
    session = AsyncMock()
    session.commit = AsyncMock()

    src = SimpleNamespace(id=1, config={}, is_active=True, status="waiting", next_sync_at=None)
    session.execute = AsyncMock(return_value=_Result(scalar_one_or_none=src))
    repo = ParsingRepository(session)

    # Retry path
    out = await repo.report_source_error(1, "err", is_broken=False)
    assert out.status == "error"
    assert out.config["retry_count"] == 1

    # Broken path
    src2 = SimpleNamespace(id=1, config={"retry_count": 3}, is_active=True, status="waiting", next_sync_at=None)
    session.execute = AsyncMock(return_value=_Result(scalar_one_or_none=src2))
    out2 = await repo.report_source_error(1, "err", is_broken=False)
    assert out2.status == "broken"
    assert out2.is_active is False
    assert out2.config["fix_required"] is True


@pytest.mark.asyncio
async def test_get_or_create_category_maps_postgres_and_sqlite():
    # Postgres path: uses insert+on_conflict_do_nothing.
    session = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.add = lambda obj: None
    session.bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

    repo = ParsingRepository(session)
    # First select finds none; second select after insert returns rows.
    session.execute = AsyncMock(side_effect=[_Result(scalars=[]), _Result(), _Result(scalars=[SimpleNamespace(external_name="a"), SimpleNamespace(external_name="b")])])
    out = await repo.get_or_create_category_maps(["a", "b"])
    assert {m.external_name for m in out} == {"a", "b"}

    # SQLite path: uses add loop + flush.
    session2 = AsyncMock()
    session2.commit = AsyncMock()
    session2.flush = AsyncMock()
    added = []
    session2.add = lambda obj: added.append(obj)
    session2.bind = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))

    repo2 = ParsingRepository(session2)
    session2.execute = AsyncMock(side_effect=[_Result(scalars=[]), _Result(scalars=[SimpleNamespace(external_name="x")])])
    out2 = await repo2.get_or_create_category_maps(["x"])
    assert [m.external_name for m in out2] == ["x"]
    assert len(added) == 1


@pytest.mark.asyncio
async def test_sync_spiders_adds_hubs_and_runtime_sources():
    session = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    added = []
    session.add = lambda obj: added.append(obj)

    # Existing hubs: empty. Existing runtime source: none.
    session.execute = AsyncMock(
        side_effect=[
            _Result(scalars=[]),  # hub keys
            _Result(scalar_one_or_none=None),  # hub by key (else branch)
            _Result(scalar_one_or_none=None),  # runtime source by key
        ]
    )
    repo = ParsingRepository(session)
    new = await repo.sync_spiders(["shop"], default_urls={"shop": "https://shop.example"})
    assert new == ["shop"]
    assert len(added) >= 2  # ParsingHub + ParsingSource


@pytest.mark.asyncio
async def test_source_status_helpers_and_logs():
    session = AsyncMock()
    session.commit = AsyncMock()
    repo = ParsingRepository(session)

    session.execute = AsyncMock(return_value=_Result(rowcount=1))
    ok = await repo.set_source_active_status(1, True)
    assert ok is True

    src = SimpleNamespace(id=1, config=None)
    session.execute = AsyncMock(return_value=_Result(scalar_one_or_none=src))
    await repo.update_source_logs(1, "logs")
    assert src.config["last_logs"] == "logs"

    src2 = SimpleNamespace(id=1, config={"last_error": "x", "fix_required": True})
    session.execute = AsyncMock(return_value=_Result(scalar_one_or_none=src2))
    await repo.reset_source_error(1)
    assert "last_error" not in src2.config


@pytest.mark.asyncio
async def test_get_aggregate_status_and_monitoring_and_stats():
    session = AsyncMock()
    repo = ParsingRepository(session)

    session.execute = AsyncMock(return_value=_Result(scalars=["queued", "waiting"]))
    assert await repo.get_aggregate_status("s") == "queued"

    row = SimpleNamespace(
        site_key="s",
        first_id=1,
        first_url="u",
        total_sources=2,
        running_count=0,
        queued_count=0,
        error_count=1,
        broken_count=0,
        last_synced_at=None,
    )
    session.execute = AsyncMock(return_value=_Result(all_rows=[row]))
    mon = await repo.get_sites_monitoring()
    assert mon[0]["status"] == "error"

    row2 = SimpleNamespace(scraped=10, new=2)
    session.execute = AsyncMock(return_value=_Result(one=row2))
    stats = await repo.get_24h_stats()
    assert stats["scraped_24h"] == 10


@pytest.mark.asyncio
async def test_get_active_workers_from_redis():
    session = AsyncMock()
    redis = AsyncMock()
    redis.keys = AsyncMock(return_value=["worker_heartbeat:1"])
    redis.get = AsyncMock(return_value=json.dumps({"worker_id": "w"}))

    repo = ParsingRepository(session, redis=redis)
    out = await repo.get_active_workers()
    assert out == [{"worker_id": "w"}]

