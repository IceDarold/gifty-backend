from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from routes import internal as internal_routes


@dataclass
class _ScalarsResult:
    items: list

    def scalars(self):
        return self

    def all(self):
        return list(self.items)


@pytest.mark.anyio
async def test_ops_discovery_run_all_requires_site_key(fake_db, fake_redis):
    with pytest.raises(HTTPException) as exc:
        await internal_routes.run_ops_discovery_all_categories(
            payload={}, db=fake_db, redis=fake_redis, _="internal"
        )
    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_ops_discovery_run_all_queues_and_skips_and_fails(fake_db, fake_redis, monkeypatch):
    cats = [
        SimpleNamespace(id=1, promoted_source_id=101, name="Shoes", url="u1", parent_url=None, state="promoted"),
        SimpleNamespace(id=2, promoted_source_id=102, name="Bags", url="u2", parent_url="p", state="promoted"),
        SimpleNamespace(id=3, promoted_source_id=None, name="Skip", url="u3", parent_url=None, state="promoted"),
    ]
    sources = [
        SimpleNamespace(id=101, url="u1", site_key="site", type="list", strategy=None, config={}, status="waiting"),
        SimpleNamespace(id=102, url="u2", site_key="site", type="list", strategy=None, config={}, status="waiting"),
    ]

    # cats query, running ids query, promoted sources query
    fake_db.execute = AsyncMock(
        side_effect=[
            _ScalarsResult(cats),
            _ScalarsResult([102]),  # source 102 is running -> skip
            _ScalarsResult(sources),
        ]
    )
    fake_db.commit = AsyncMock()

    repo = SimpleNamespace(set_queued=AsyncMock())
    monkeypatch.setattr(internal_routes, "ParsingRepository", lambda db: repo)
    monkeypatch.setattr(internal_routes, "_fetch_rabbit_queued_task_ids", AsyncMock(return_value=(set(), {101})))
    monkeypatch.setattr(internal_routes, "_fetch_rabbit_queue_stats", AsyncMock(return_value={"status": "ok"}))
    monkeypatch.setattr(internal_routes, "_publish_ops_event", AsyncMock())

    # First cat already queued in rabbit -> skip; second running -> skip; third no source -> skipped; nothing queued.
    monkeypatch.setattr("app.utils.rabbitmq.publish_parsing_task", lambda task: True)

    resp = await internal_routes.run_ops_discovery_all_categories(
        payload={"site_key": "site", "limit": 100, "states": ["promoted"]},
        db=fake_db,
        redis=fake_redis,
        _="internal",
    )
    assert resp["status"] == "ok"
    assert resp["selected"] == 3
    assert resp["queued"] == 0
    assert resp["skipped"] == 3

    # Now allow 101 to queue, but fail publish; keep 102 not running and not queued.
    fake_db.execute = AsyncMock(
        side_effect=[
            _ScalarsResult(cats[:2]),
            _ScalarsResult([]),
            _ScalarsResult(sources),
        ]
    )
    monkeypatch.setattr(internal_routes, "_fetch_rabbit_queued_task_ids", AsyncMock(return_value=(set(), set())))

    def _publish(task):
        return int(task["source_id"]) != 101

    monkeypatch.setattr("app.utils.rabbitmq.publish_parsing_task", _publish)
    resp2 = await internal_routes.run_ops_discovery_all_categories(
        payload={"site_key": "site", "limit": 100},
        db=fake_db,
        redis=fake_redis,
        _="internal",
    )
    assert resp2["selected"] == 2
    assert resp2["queued"] == 1
    assert resp2["failed"] == 1
    repo.set_queued.assert_awaited_with(102)


@pytest.mark.anyio
async def test_bulk_update_ops_sources_updates_rowcount(fake_db, monkeypatch):
    res = SimpleNamespace(rowcount=3)
    fake_db.execute = AsyncMock(return_value=res)
    fake_db.commit = AsyncMock()

    body = await internal_routes.bulk_update_ops_sources(
        payload={"source_ids": [1, 2, 3], "is_active": True, "priority": 10},
        db=fake_db,
        _="internal",
    )
    assert body == {"status": "ok", "updated": 3}


@pytest.mark.anyio
async def test_bulk_update_ops_sources_noop_paths(fake_db):
    body = await internal_routes.bulk_update_ops_sources(payload={}, db=fake_db, _="internal")
    assert body == {"status": "ok", "updated": 0}

    body2 = await internal_routes.bulk_update_ops_sources(payload={"source_ids": [1]}, db=fake_db, _="internal")
    assert body2 == {"status": "ok", "updated": 0}

