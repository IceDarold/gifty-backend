from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from routes import internal as internal_routes
from app.models import ParsingSource
from tests.routes.internal.conftest import assert_ok


def _source(source_id: int = 1) -> ParsingSource:
    src = ParsingSource(
        url=f"https://example.com/{source_id}",
        type="list",
        site_key="mrgeek",
        strategy="discovery",
        priority=50,
        refresh_interval_hours=24,
        last_synced_at=None,
        next_sync_at=datetime.now(timezone.utc),
        is_active=True,
        status="waiting",
        category_id=None,
        config={},
    )
    src.id = source_id
    return src


@pytest.fixture
def parsing_repo_mock(monkeypatch):
    repo = SimpleNamespace(
        get_sites_monitoring=AsyncMock(return_value=[{"site_key": "mrgeek", "total_sources": 1, "status": "waiting"}]),
        get_24h_stats=AsyncMock(return_value={"scraped_24h": 1, "new_24h": 1}),
        get_all_sources=AsyncMock(return_value=[_source(1)]),
        upsert_source=AsyncMock(return_value=_source(2)),
        get_source_by_id=AsyncMock(return_value=_source(1)),
        get_source=AsyncMock(return_value=_source(1)),
        update_source=AsyncMock(return_value=_source(1)),
        set_source_active_status=AsyncMock(return_value=True),
        reset_source_error=AsyncMock(return_value=None),
        get_unmapped_categories=AsyncMock(return_value=[SimpleNamespace(external_name="Gifts")]),
        update_category_mappings=AsyncMock(return_value=1),
        create_parsing_run=AsyncMock(return_value=SimpleNamespace(id=10)),
        set_queued=AsyncMock(return_value=None),
        update_parsing_run=AsyncMock(return_value=None),
        report_source_error=AsyncMock(return_value=_source(1)),
        update_source_stats=AsyncMock(return_value=None),
        get_active_workers=AsyncMock(return_value=[{"worker_id": "w1"}]),
        get_source_history=AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(internal_routes, "ParsingRepository", lambda *args, **kwargs: repo, raising=True)
    monkeypatch.setattr(internal_routes, "_sync_hub_from_hub_source", AsyncMock(return_value=None), raising=True)
    return repo


@pytest.fixture
def catalog_repo_mock(monkeypatch):
    repo = SimpleNamespace(
        delete_products_by_site=AsyncMock(return_value=3),
    )
    monkeypatch.setattr(internal_routes, "PostgresCatalogRepository", lambda *args, **kwargs: repo, raising=True)
    return repo


def test_scoring_endpoints_are_gone(client):
    resp = client.get("/api/v1/internal/scoring/tasks")
    assert resp.status_code == 410
    resp2 = client.post("/api/v1/internal/scoring/submit")
    assert resp2.status_code == 410


def test_monitoring_and_stats(client, parsing_repo_mock):
    resp = client.get("/api/v1/internal/monitoring")
    assert resp.status_code == 200
    assert resp.json()[0]["site_key"] == "mrgeek"

    resp2 = client.get("/api/v1/internal/stats")
    assert resp2.status_code == 200
    assert resp2.json()["scraped_24h"] == 1


def test_sources_list_and_upsert(client, parsing_repo_mock):
    resp = client.get("/api/v1/internal/sources")
    assert resp.status_code == 200
    assert resp.json()[0]["site_key"] == "mrgeek"

    resp2 = client.post(
        "/api/v1/internal/sources",
        json={"url": "https://example.com/2", "type": "hub", "site_key": "mrgeek", "strategy": "discovery"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["id"] == 2


def test_source_details_and_patch_and_toggle(client, parsing_repo_mock):
    resp = client.get("/api/v1/internal/sources/1")
    assert resp.status_code == 200
    assert resp.json()["id"] == 1

    resp2 = client.patch("/api/v1/internal/sources/1", json={"priority": 10})
    assert resp2.status_code == 200

    resp3 = client.post("/api/v1/internal/sources/1/toggle", json={"is_active": False})
    body = assert_ok(resp3)
    assert body["is_active"] is False


def test_categories_tasks_and_submit(client, parsing_repo_mock):
    tasks = client.get("/api/v1/internal/categories/tasks")
    assert tasks.status_code == 200
    assert tasks.json()[0]["external_name"] == "Gifts"

    resp = client.post(
        "/api/v1/internal/categories/submit",
        json={"results": [{"external_name": "Gifts", "internal_category_id": 1}]},
    )
    assert_ok(resp)


def test_clear_source_data(client, parsing_repo_mock, catalog_repo_mock):
    resp = client.delete("/api/v1/internal/sources/1/data")
    body = assert_ok(resp)
    assert body["deleted"] == 3
