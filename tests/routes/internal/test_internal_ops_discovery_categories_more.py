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


@dataclass
class _ScalarResult:
    value: object

    def scalar(self):
        return self.value


@dataclass
class _ScalarsAllResult:
    items: list

    def scalars(self):
        return SimpleNamespace(all=lambda: list(self.items))


@dataclass
class _AllResult:
    rows: list

    def all(self):
        return list(self.rows)


@pytest.mark.anyio
async def test_get_ops_discovery_category_details_404(fake_db):
    fake_db.execute = AsyncMock(return_value=_ScalarOneOrNoneResult(None))
    with pytest.raises(internal_routes.HTTPException) as exc:
        await internal_routes.get_ops_discovery_category_details(category_id=1, db=fake_db, _="internal")
    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_get_ops_discovery_category_details_with_source_runs_and_trend(fake_db):
    now = datetime(2025, 1, 1, tzinfo=timezone.utc)
    category = SimpleNamespace(
        id=7,
        hub_id=1,
        site_key="s",
        name="Cat",
        url="u",
        parent_url="p",
        state="promoted",
        promoted_source_id=10,
        created_at=now,
        updated_at=now,
    )
    source = SimpleNamespace(
        id=10,
        status="waiting",
        is_active=True,
        priority=5,
        refresh_interval_hours=24,
        last_synced_at=now,
    )
    runs = [
        SimpleNamespace(
            id=1,
            status="completed",
            items_new=3,
            items_scraped=10,
            error_message=None,
            duration_seconds=1.2,
            created_at=now,
            updated_at=now,
        )
    ]
    trend_rows = [
        SimpleNamespace(date=now.date(), items_new=3, items_scraped=10),
    ]

    fake_db.execute = AsyncMock(
        side_effect=[
            _ScalarOneOrNoneResult(category),
            _ScalarResult(11),  # products_total
            _ScalarOneOrNoneResult(source),
            _ScalarsAllResult(runs),
            _AllResult(trend_rows),
        ]
    )

    out = await internal_routes.get_ops_discovery_category_details(category_id=7, db=fake_db, _="internal")
    assert out["status"] == "ok"
    assert out["item"]["products_total"] == 11
    assert out["item"]["runtime_source"]["id"] == 10
    assert out["item"]["recent_runs"][0]["id"] == 1
    assert out["item"]["trend"][0]["items_new"] == 3


@pytest.mark.anyio
async def test_reject_and_reactivate_empty_ids_fast_path(fake_db):
    out1 = await internal_routes.reject_ops_discovery_categories(category_ids=[], db=fake_db, _="internal")
    out2 = await internal_routes.reactivate_ops_discovery_categories(category_ids=[], db=fake_db, _="internal")
    assert out1 == {"status": "ok", "updated": 0}
    assert out2 == {"status": "ok", "updated": 0}


@pytest.mark.anyio
async def test_run_ops_discovery_category_now_happy_path(fake_db, fake_redis, monkeypatch):
    now = datetime(2025, 1, 1, tzinfo=timezone.utc)
    category = SimpleNamespace(
        id=7,
        site_key="s",
        name="Cat",
        url="u",
        parent_url="p",
        state="promoted",
        promoted_source_id=10,
    )
    source = SimpleNamespace(
        id=10,
        url="u",
        site_key="s",
        type="list",
        strategy="deep",
        config={},
        is_active=False,
        status="disabled",
        priority=0,
        refresh_interval_hours=0,
        last_synced_at=now,
    )

    fake_db.execute = AsyncMock(
        side_effect=[
            _ScalarOneOrNoneResult(category),
            _ScalarOneOrNoneResult(source),
        ]
    )
    fake_db.commit = AsyncMock()
    fake_db.refresh = AsyncMock()

    repo = SimpleNamespace(set_queued=AsyncMock(return_value=True))
    monkeypatch.setattr(internal_routes, "ParsingRepository", lambda db: repo, raising=True)

    monkeypatch.setattr("app.utils.rabbitmq.publish_parsing_task", lambda task: True)
    monkeypatch.setattr(internal_routes, "_fetch_rabbit_queue_stats", AsyncMock(return_value={"status": "ok"}))

    out = await internal_routes.run_ops_discovery_category_now(category_id=7, db=fake_db, redis=fake_redis, _="internal")
    assert out["status"] == "ok"
    assert out["queued"] is True
    assert source.is_active is True
    assert source.status == "waiting"
    assert source.config["discovery_name"] == "Cat"
    assert source.config["parent_url"] == "p"
    assert source.config["discovered_category_id"] == 7
    repo.set_queued.assert_awaited()


@pytest.mark.anyio
async def test_run_ops_discovery_category_now_conflict_when_not_promoted(fake_db, fake_redis):
    category = SimpleNamespace(id=7, site_key="s", state="new", promoted_source_id=None)
    fake_db.execute = AsyncMock(return_value=_ScalarOneOrNoneResult(category))
    with pytest.raises(internal_routes.HTTPException) as exc:
        await internal_routes.run_ops_discovery_category_now(category_id=7, db=fake_db, redis=fake_redis, _="internal")
    assert exc.value.status_code == 409
