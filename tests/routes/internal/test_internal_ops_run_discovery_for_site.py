from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from routes import internal as internal_routes


@dataclass
class _ScalarOneOrNoneResult:
    value: object

    def scalar_one_or_none(self):
        return self.value


@pytest.mark.anyio
async def test_run_discovery_for_site_404_when_hub_missing(fake_db, fake_redis):
    fake_db.execute = AsyncMock(return_value=_ScalarOneOrNoneResult(None))
    with pytest.raises(internal_routes.HTTPException) as exc:
        await internal_routes.run_discovery_for_site(site_key="s", db=fake_db, redis=fake_redis, _="internal")
    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_run_discovery_for_site_updates_existing_source_and_queues(fake_db, fake_redis, monkeypatch):
    now = datetime(2025, 1, 1, tzinfo=timezone.utc)
    hub = SimpleNamespace(site_key="s", url="u", strategy="discovery", is_active=True, config={"x": 1}, status="waiting", next_sync_at=None)
    source = SimpleNamespace(id=10, site_key="s", url="old", type="hub", strategy="old", is_active=False, config={"y": 2})

    fake_db.add = lambda _obj: None
    fake_db.commit = AsyncMock()
    fake_db.refresh = AsyncMock()
    fake_db.execute = AsyncMock(side_effect=[_ScalarOneOrNoneResult(hub), _ScalarOneOrNoneResult(source)])

    repo = SimpleNamespace(set_queued=AsyncMock())
    monkeypatch.setattr(internal_routes, "ParsingRepository", lambda db: repo, raising=True)
    monkeypatch.setattr("app.utils.rabbitmq.publish_parsing_task", lambda task: True)
    monkeypatch.setattr(internal_routes, "_fetch_rabbit_queue_stats", AsyncMock(return_value={"status": "ok"}))

    out = await internal_routes.run_discovery_for_site(site_key="s", db=fake_db, redis=fake_redis, _="internal")
    assert out["status"] == "ok"
    assert out["queued"] is True
    assert source.url == "u"
    assert source.strategy == "discovery"
    assert source.is_active is True
    repo.set_queued.assert_awaited()


@pytest.mark.anyio
async def test_run_discovery_for_site_publish_failure_returns_500(fake_db, fake_redis, monkeypatch):
    hub = SimpleNamespace(site_key="s", url="u", strategy="discovery", is_active=True, config={}, status="waiting", next_sync_at=None)
    source = SimpleNamespace(id=10, site_key="s", url="u", type="hub", strategy="discovery", is_active=True, config={})

    fake_db.add = lambda _obj: None
    fake_db.commit = AsyncMock()
    fake_db.refresh = AsyncMock()
    fake_db.execute = AsyncMock(side_effect=[_ScalarOneOrNoneResult(hub), _ScalarOneOrNoneResult(source)])

    monkeypatch.setattr(internal_routes, "ParsingRepository", lambda db: SimpleNamespace(set_queued=AsyncMock()), raising=True)
    monkeypatch.setattr("app.utils.rabbitmq.publish_parsing_task", lambda task: False)

    with pytest.raises(internal_routes.HTTPException) as exc:
        await internal_routes.run_discovery_for_site(site_key="s", db=fake_db, redis=fake_redis, _="internal")
    assert exc.value.status_code == 500


@pytest.mark.anyio
async def test_run_discovery_for_site_creates_anchor_source_when_missing(fake_db, fake_redis, monkeypatch):
    hub = SimpleNamespace(site_key="s", url="u", strategy=None, is_active=False, config={}, status="waiting", next_sync_at=None)
    fake_db.add = lambda _obj: None
    fake_db.commit = AsyncMock()
    async def _refresh(obj):
        # emulate DB assigning PK on insert
        if getattr(obj, "id", None) is None:
            obj.id = 123
    fake_db.refresh = AsyncMock(side_effect=_refresh)
    fake_db.execute = AsyncMock(side_effect=[_ScalarOneOrNoneResult(hub), _ScalarOneOrNoneResult(None)])

    monkeypatch.setattr(internal_routes, "ParsingRepository", lambda db: SimpleNamespace(set_queued=AsyncMock()), raising=True)
    monkeypatch.setattr("app.utils.rabbitmq.publish_parsing_task", lambda task: True)
    monkeypatch.setattr(internal_routes, "_fetch_rabbit_queue_stats", AsyncMock(return_value={"status": "error"}))

    out = await internal_routes.run_discovery_for_site(site_key="s", db=fake_db, redis=fake_redis, _="internal")
    assert out["status"] == "ok"
