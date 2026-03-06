from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.models import ParsingSource
from routes import internal as internal_routes


@dataclass
class _ScalarsResult:
    items: list

    def scalars(self):
        return self

    def all(self):
        return list(self.items)

    def scalar_one_or_none(self):
        return self.items[0] if self.items else None


@dataclass
class _AllResult:
    rows: list

    def all(self):
        return list(self.rows)


@pytest.mark.anyio
async def test_toggle_parser_404(fake_db, monkeypatch):
    repo = SimpleNamespace(
        get_source_by_id=AsyncMock(return_value=None),
        set_source_active_status=AsyncMock(),
        reset_source_error=AsyncMock(),
    )
    monkeypatch.setattr(internal_routes, "ParsingRepository", lambda db: repo)

    with pytest.raises(HTTPException) as exc:
        await internal_routes.toggle_parser(123, is_active=True, db=fake_db, _="internal")
    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_toggle_parser_resets_error_when_enabling(fake_db, monkeypatch):
    source = SimpleNamespace(id=1, site_key="s", config={}, is_active=False)
    repo = SimpleNamespace(
        get_source_by_id=AsyncMock(side_effect=[source, source]),
        set_source_active_status=AsyncMock(),
        reset_source_error=AsyncMock(),
    )
    sync = AsyncMock()
    monkeypatch.setattr(internal_routes, "ParsingRepository", lambda db: repo)
    monkeypatch.setattr(internal_routes, "_sync_hub_from_hub_source", sync)

    resp = await internal_routes.toggle_parser(1, is_active=True, db=fake_db, _="internal")
    assert resp == {"status": "ok", "is_active": True}
    repo.reset_source_error.assert_awaited_once_with(1)
    sync.assert_awaited()
    fake_db.commit.assert_awaited()


@pytest.mark.anyio
async def test_report_parsing_status_running_sets_started_at_and_emits_event(fake_db, fake_redis, monkeypatch):
    source = SimpleNamespace(id=1, site_key="site", config={})
    repo = SimpleNamespace(
        set_source_status=AsyncMock(),
        get_source_by_id=AsyncMock(return_value=source),
    )
    publish = AsyncMock()
    monkeypatch.setattr(internal_routes, "ParsingRepository", lambda db: repo)
    monkeypatch.setattr(internal_routes, "_sync_hub_from_hub_source", AsyncMock())
    monkeypatch.setattr(internal_routes, "_publish_ops_event", publish)

    resp = await internal_routes.report_parsing_status(
        1, status="running", run_id=7, db=fake_db, redis=fake_redis, _="internal"
    )
    assert resp == {"status": "ok"}
    assert "run_started_at" in source.config
    publish.assert_awaited()


@pytest.mark.anyio
async def test_report_parsing_status_waiting_persists_run_and_clears_stats(fake_db, fake_redis, monkeypatch):
    await fake_redis.set("run_stats:1", json.dumps({"items_scraped": 12, "items_new": 5}))
    started_at = datetime.now(timezone.utc).isoformat()
    source = SimpleNamespace(id=1, site_key="site", config={"last_logs": "ERROR boom", "run_started_at": started_at})
    completed_run = SimpleNamespace(id=42)
    repo = SimpleNamespace(
        set_source_status=AsyncMock(),
        get_source_by_id=AsyncMock(return_value=source),
        create_parsing_run=AsyncMock(return_value=completed_run),
    )
    publish = AsyncMock()
    monkeypatch.setattr(internal_routes, "ParsingRepository", lambda db: repo)
    monkeypatch.setattr(internal_routes, "_sync_hub_from_hub_source", AsyncMock())
    monkeypatch.setattr(internal_routes, "_publish_ops_event", publish)

    resp = await internal_routes.report_parsing_status(
        1, status="waiting", run_id=42, db=fake_db, redis=fake_redis, _="internal"
    )
    assert resp == {"status": "ok"}
    assert await fake_redis.get("run_stats:1") is None
    repo.create_parsing_run.assert_awaited()
    publish.assert_awaited()


@pytest.mark.anyio
async def test_report_parsing_status_waiting_tolerates_bad_stats_json(fake_db, fake_redis, monkeypatch):
    await fake_redis.set("run_stats:1", "{not-json")
    source = SimpleNamespace(id=1, site_key="site", config={"last_logs": "ok", "run_started_at": "bad"})
    repo = SimpleNamespace(
        set_source_status=AsyncMock(),
        get_source_by_id=AsyncMock(return_value=source),
        create_parsing_run=AsyncMock(return_value=SimpleNamespace(id=1)),
    )
    monkeypatch.setattr(internal_routes, "ParsingRepository", lambda db: repo)
    monkeypatch.setattr(internal_routes, "_sync_hub_from_hub_source", AsyncMock())
    monkeypatch.setattr(internal_routes, "_publish_ops_event", AsyncMock())

    resp = await internal_routes.report_parsing_status(
        1, status="waiting", run_id=None, db=fake_db, redis=fake_redis, _="internal"
    )
    assert resp == {"status": "ok"}
    repo.create_parsing_run.assert_awaited()


@pytest.mark.anyio
async def test_report_parsing_logs_updates_hub_and_emits_log_chunk(fake_db, fake_redis, monkeypatch):
    source = SimpleNamespace(id=1, site_key="site", type="hub")
    hub = SimpleNamespace(site_key="site", config={})
    repo = SimpleNamespace(
        update_source_logs=AsyncMock(),
        get_source_by_id=AsyncMock(return_value=source),
        update_parsing_run=AsyncMock(),
    )
    publish = AsyncMock()
    fake_db.execute = AsyncMock(return_value=_ScalarsResult([hub]))

    monkeypatch.setattr(internal_routes, "ParsingRepository", lambda db: repo)
    monkeypatch.setattr(internal_routes, "_publish_ops_event", publish)

    resp = await internal_routes.report_parsing_logs(
        1, logs="some error line", run_id=9, db=fake_db, redis=fake_redis, _="internal"
    )
    assert resp == {"status": "ok"}
    assert hub.config.get("last_logs")
    repo.update_parsing_run.assert_awaited_once()
    publish.assert_awaited()


@pytest.mark.anyio
async def test_get_parsing_source_details_hub_aggregates_related_sources(fake_db, monkeypatch):
    now = datetime.now(timezone.utc)
    hub_source = ParsingSource(
        id=10,
        site_key="site",
        url="https://example.com",
        type="hub",
        status="waiting",
        is_active=True,
        config={},
        created_at=now,
        next_sync_at=now,
        last_synced_at=now,
    )
    list_source = ParsingSource(
        id=11,
        site_key="site",
        url="https://example.com/cat",
        type="list",
        status="waiting",
        is_active=True,
        config={"discovery_name": "Cats"},
        created_at=now,
        next_sync_at=now,
        last_synced_at=now,
    )
    discovered = SimpleNamespace(
        id=99,
        site_key="site",
        url=list_source.url,
        state="promoted",
        name="Cats",
        parent_url="https://example.com",
        promoted_source_id=list_source.id,
        created_at=now,
    )
    history_day = SimpleNamespace(day=datetime.now(timezone.utc).date(), items_new=2, items_scraped=3)

    repo = SimpleNamespace(
        get_source_by_id=AsyncMock(return_value=hub_source),
        get_total_products_count=AsyncMock(return_value=100),
        get_aggregate_status=AsyncMock(return_value="waiting"),
        get_last_full_cycle_stats=AsyncMock(return_value=5),
        get_aggregate_history=AsyncMock(return_value=[history_day]),
        get_all_sources=AsyncMock(return_value=[hub_source, list_source]),
    )
    # discovered categories query, then totals query
    fake_db.execute = AsyncMock(
        side_effect=[
            _ScalarsResult([discovered]),
            _AllResult([("Cats", 7)]),
        ]
    )

    monkeypatch.setattr(internal_routes, "ParsingRepository", lambda db: repo)

    data = await internal_routes.get_parsing_source_details(10, db=fake_db, _="internal")
    assert data["id"] == 10
    assert data["site_key"] == "site"
    assert data["total_items"] == 100
    assert data["aggregate_history"]
    assert data["related_sources"]
    assert data["related_sources"][0]["total_items"] == 7


@pytest.mark.anyio
async def test_get_parsing_source_details_list_includes_history(fake_db, monkeypatch):
    list_source = ParsingSource(
        id=11,
        site_key="site",
        url="https://example.com/cat",
        type="list",
        status="waiting",
        is_active=True,
        config={"discovery_name": "Cats"},
        created_at=datetime.now(timezone.utc),
    )
    history = [
        SimpleNamespace(
            id=1,
            source_id=11,
            status="completed",
            items_scraped=10,
            items_new=2,
            error_message=None,
            created_at=datetime.now(timezone.utc),
        )
    ]
    repo = SimpleNamespace(
        get_source_by_id=AsyncMock(return_value=list_source),
        get_total_category_products_count=AsyncMock(return_value=50),
        get_source_history=AsyncMock(return_value=history),
    )
    monkeypatch.setattr(internal_routes, "ParsingRepository", lambda db: repo)

    data = await internal_routes.get_parsing_source_details(11, db=fake_db, _="internal")
    assert data["id"] == 11
    assert data["total_items"] == 50
    assert data["history"][0]["items_new"] == 2
