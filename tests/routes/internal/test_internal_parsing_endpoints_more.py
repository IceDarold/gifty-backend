from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.schemas.parsing import ParsingSourceUpdate, SpiderSyncRequest
from routes import internal as internal_routes


@pytest.mark.anyio
async def test_get_source_products_endpoint_404(fake_db, monkeypatch):
    parsing_repo = SimpleNamespace(get_source=AsyncMock(return_value=None))
    monkeypatch.setattr("app.repositories.parsing.ParsingRepository", lambda db: parsing_repo)
    monkeypatch.setattr("app.repositories.catalog.PostgresCatalogRepository", lambda db: SimpleNamespace())

    with pytest.raises(HTTPException) as exc:
        await internal_routes.get_source_products_endpoint(1, limit=10, offset=0, db=fake_db, _="internal")
    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_get_source_products_endpoint_filters_by_site_and_category(fake_db, monkeypatch):
    source = SimpleNamespace(site_key="site", config={"discovery_name": "Cats"})
    parsing_repo = SimpleNamespace(get_source=AsyncMock(return_value=source))
    catalog_repo = SimpleNamespace(
        get_products=AsyncMock(return_value=[{"id": "p1"}]),
        count_products=AsyncMock(return_value=3),
    )
    monkeypatch.setattr("app.repositories.parsing.ParsingRepository", lambda db: parsing_repo)
    monkeypatch.setattr("app.repositories.catalog.PostgresCatalogRepository", lambda db: catalog_repo)

    out = await internal_routes.get_source_products_endpoint(1, limit=10, offset=0, db=fake_db, _="internal")
    assert out["total"] == 3
    catalog_repo.get_products.assert_awaited_once()
    catalog_repo.count_products.assert_awaited_once()


@pytest.mark.anyio
async def test_update_parsing_source_endpoint_updates_and_syncs(fake_db, monkeypatch):
    source = SimpleNamespace(id=1, type="hub", site_key="s", config={})
    repo = SimpleNamespace(update_source=AsyncMock(return_value=source))
    monkeypatch.setattr(internal_routes, "ParsingRepository", lambda db: repo)
    monkeypatch.setattr(internal_routes, "_sync_hub_from_hub_source", AsyncMock())

    out = await internal_routes.update_parsing_source_endpoint(
        1,
        data=ParsingSourceUpdate(url="u", type=None, strategy=None, priority=None, refresh_interval_hours=None, is_active=None, config=None),
        db=fake_db,
        _="internal",
    )
    assert out is source
    fake_db.commit.assert_awaited()
    fake_db.refresh.assert_awaited_with(source)


@pytest.mark.anyio
async def test_update_parsing_source_endpoint_404(fake_db, monkeypatch):
    repo = SimpleNamespace(update_source=AsyncMock(return_value=None))
    monkeypatch.setattr(internal_routes, "ParsingRepository", lambda db: repo)
    with pytest.raises(HTTPException) as exc:
        await internal_routes.update_parsing_source_endpoint(1, data=ParsingSourceUpdate(), db=fake_db, _="internal")
    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_sync_spiders_endpoint_notifies_when_new(fake_db, monkeypatch):
    repo = SimpleNamespace(
        sync_spiders=AsyncMock(return_value=["s1", "s2"]),
        mark_missing_spiders=AsyncMock(return_value={"disabled": [], "still_missing": []}),
    )
    notifier = SimpleNamespace(notify=AsyncMock())
    monkeypatch.setattr(internal_routes, "ParsingRepository", lambda db: repo)
    monkeypatch.setattr(internal_routes, "get_notification_service", lambda: notifier)

    out = await internal_routes.sync_spiders_endpoint(
        SpiderSyncRequest(available_spiders=["s1", "s2"], default_urls={"s1": "u"}),
        db=fake_db,
        _="internal",
    )
    assert out["new_spiders"] == ["s1", "s2"]
    # Notifications are fire-and-forget (scheduled via create_task).
    await asyncio.sleep(0)
    notifier.notify.assert_awaited()
    repo.mark_missing_spiders.assert_awaited()


@pytest.mark.anyio
async def test_sync_spiders_endpoint_no_new_no_notify(fake_db, monkeypatch):
    repo = SimpleNamespace(
        sync_spiders=AsyncMock(return_value=[]),
        mark_missing_spiders=AsyncMock(return_value={"disabled": [], "still_missing": []}),
    )
    notifier = SimpleNamespace(notify=AsyncMock())
    monkeypatch.setattr(internal_routes, "ParsingRepository", lambda db: repo)
    monkeypatch.setattr(internal_routes, "get_notification_service", lambda: notifier)
    out = await internal_routes.sync_spiders_endpoint(
        SpiderSyncRequest(available_spiders=["s1"], default_urls=None), db=fake_db, _="internal"
    )
    assert out["new_spiders"] == []
    await asyncio.sleep(0)
    assert notifier.notify.await_count == 0
    repo.mark_missing_spiders.assert_awaited()


@pytest.mark.anyio
async def test_backlog_endpoints(fake_db, monkeypatch):
    repo = SimpleNamespace(
        get_discovered_categories=AsyncMock(return_value=[{"id": 1}]),
        activate_sources=AsyncMock(return_value=2),
        count_promoted_categories_today=AsyncMock(return_value=5),
    )
    monkeypatch.setattr(internal_routes, "ParsingRepository", lambda db: repo)

    out = await internal_routes.get_discovery_backlog(limit=10, db=fake_db, _="internal")
    assert out == [{"id": 1}]

    out2 = await internal_routes.activate_backlog_sources(payload={"category_ids": [1, 2]}, db=fake_db, _="internal")
    assert out2["activated_count"] == 2

    out3 = await internal_routes.get_backlog_stats(db=fake_db, _="internal")
    assert out3["promoted_today"] == 5
    assert out3["backlog_size"] == 1


@pytest.mark.anyio
async def test_run_all_spiders_endpoint_counts_queued_and_failed(fake_db, fake_redis, monkeypatch):
    sources = [
        SimpleNamespace(id=1, url="u1", site_key="s", type="hub", strategy="deep", config={}),
        SimpleNamespace(id=2, url="u2", site_key="s", type="hub", strategy="deep", config={}),
    ]
    repo = SimpleNamespace(get_all_active_sources=AsyncMock(return_value=sources), set_queued=AsyncMock())
    monkeypatch.setattr(internal_routes, "ParsingRepository", lambda db: repo)
    monkeypatch.setattr(internal_routes, "_publish_ops_event", AsyncMock())
    monkeypatch.setattr(internal_routes, "_fetch_rabbit_queue_stats", AsyncMock(return_value={"status": "ok"}))

    def _publish(task):
        return int(task["source_id"]) == 1

    monkeypatch.setattr("app.utils.rabbitmq.publish_parsing_task", _publish)

    out = await internal_routes.run_all_spiders_endpoint(db=fake_db, redis=fake_redis, _="internal")
    assert out["queued"] == 1
    assert out["failed"] == 1
    repo.set_queued.assert_awaited_once_with(1)


@pytest.mark.anyio
async def test_clear_source_data_endpoint_404_and_ok(fake_db, monkeypatch):
    parsing_repo = SimpleNamespace(get_source=AsyncMock(return_value=None))
    monkeypatch.setattr(internal_routes, "ParsingRepository", lambda db: parsing_repo)
    monkeypatch.setattr(internal_routes, "PostgresCatalogRepository", lambda db: SimpleNamespace(delete_products_by_site=AsyncMock()))

    with pytest.raises(HTTPException) as exc:
        await internal_routes.clear_source_data_endpoint(1, db=fake_db, _="internal")
    assert exc.value.status_code == 404

    parsing_repo.get_source = AsyncMock(return_value=SimpleNamespace(site_key="site"))
    catalog_repo = SimpleNamespace(delete_products_by_site=AsyncMock(return_value=7))
    monkeypatch.setattr(internal_routes, "PostgresCatalogRepository", lambda db: catalog_repo)
    out = await internal_routes.clear_source_data_endpoint(1, db=fake_db, _="internal")
    assert out["deleted"] == 7


class _TinyPubSub:
    def __init__(self, messages: list[dict]):
        self._messages = list(messages)

    async def subscribe(self, channel: str):
        return None

    async def unsubscribe(self, channel: str):
        return None

    async def close(self):
        return None

    async def get_message(self, *, ignore_subscribe_messages: bool = True, timeout: float = 0.0):
        await asyncio.sleep(0)
        return self._messages.pop(0) if self._messages else None


@pytest.mark.anyio
async def test_stream_source_logs_sends_connected_when_no_buffer():
    pubsub = _TinyPubSub(messages=[{"type": "message", "data": "m1"}, None])
    redis = SimpleNamespace(lrange=AsyncMock(return_value=[]), pubsub=lambda: pubsub)
    resp = await internal_routes.stream_source_logs(1, redis=redis)
    agen = resp.body_iterator
    first = await agen.__anext__()
    second = await agen.__anext__()
    third = await agen.__anext__()
    assert "CONNECTED" in first
    assert "m1" in second
    assert ":ping" in third
    await agen.aclose()
