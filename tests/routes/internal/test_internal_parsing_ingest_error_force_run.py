from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.schemas.parsing import IngestBatchRequest, ParsingErrorReport, ScrapedCategory, ScrapedProduct
from routes import internal as internal_routes


@pytest.mark.anyio
async def test_ingest_batch_updates_run_stats_and_emits_catalog_event(fake_db, fake_redis, monkeypatch):
    # Pre-seed invalid JSON to cover decode fallback.
    await fake_redis.set("run_stats:1", "{bad-json")

    class _Svc:
        def __init__(self, db, redis):
            self.ingest_products = AsyncMock(return_value=2)
            self.ingest_categories = AsyncMock(return_value=1)

    source = SimpleNamespace(id=1, site_key="site")
    repo = SimpleNamespace(
        get_source_by_id=AsyncMock(return_value=source),
        update_source_stats=AsyncMock(),
    )

    publish = AsyncMock()
    monkeypatch.setattr(internal_routes, "IngestionService", _Svc)
    monkeypatch.setattr(internal_routes, "ParsingRepository", lambda db: repo)
    monkeypatch.setattr(internal_routes, "_publish_ops_event", publish)

    req = IngestBatchRequest(
        items=[
            ScrapedProduct(
                title="t",
                product_url="https://p",
                site_key="site",
            )
        ],
        categories=[
            ScrapedCategory(
                name="c",
                url="https://c",
                parent_url=None,
                site_key="site",
            )
        ],
        source_id=1,
        run_id=7,
        stats={},
    )

    out = await internal_routes.ingest_batch(req, db=fake_db, redis=fake_redis, _="internal")
    assert out["status"] == "ok"
    assert out["items_ingested"] == 2
    assert out["categories_ingested"] == 1

    raw = await fake_redis.get("run_stats:1")
    payload = json.loads(raw)
    assert payload["items_scraped"] == 1
    assert payload["items_new"] == 2
    assert payload["categories_ingested"] == 1
    publish.assert_awaited()


@pytest.mark.anyio
async def test_ingest_batch_discovery_marks_source(fake_db, fake_redis, monkeypatch):
    class _Svc:
        def __init__(self, db, redis):
            self.ingest_products = AsyncMock(return_value=0)
            self.ingest_categories = AsyncMock(return_value=3)

    repo = SimpleNamespace(
        get_source_by_id=AsyncMock(return_value=SimpleNamespace(id=1, site_key="site")),
        update_source_stats=AsyncMock(),
    )
    monkeypatch.setattr(internal_routes, "IngestionService", _Svc)
    monkeypatch.setattr(internal_routes, "ParsingRepository", lambda db: repo)
    monkeypatch.setattr(internal_routes, "_publish_ops_event", AsyncMock())

    req = IngestBatchRequest(
        items=[],
        categories=[
            ScrapedCategory(name="c1", url="u1", parent_url=None, site_key="site"),
        ],
        source_id=1,
        run_id=None,
        stats={},
    )
    out = await internal_routes.ingest_batch(req, db=fake_db, redis=fake_redis, _="internal")
    assert out["status"] == "ok"
    repo.update_source_stats.assert_awaited_once()


@pytest.mark.anyio
async def test_report_parsing_error_creates_run_and_clears_stats(fake_db, fake_redis, monkeypatch):
    await fake_redis.set("run_stats:1", json.dumps({"items_scraped": 5, "items_new": 2}))
    now = datetime.now(timezone.utc).isoformat()
    source = SimpleNamespace(site_key="site", url="u", config={"last_logs": "log", "run_started_at": now})

    repo = SimpleNamespace(
        report_source_error=AsyncMock(return_value=source),
        create_parsing_run=AsyncMock(return_value=SimpleNamespace(id=123)),
    )
    monkeypatch.setattr(internal_routes, "ParsingRepository", lambda db: repo)
    monkeypatch.setattr(internal_routes, "_publish_ops_event", AsyncMock())
    monkeypatch.setattr(internal_routes, "_sync_hub_from_hub_source", AsyncMock())

    out = await internal_routes.report_parsing_error(
        1,
        report=ParsingErrorReport(error="boom", is_broken=False),
        run_id=None,
        db=fake_db,
        redis=fake_redis,
        _="internal",
    )
    assert out == {"status": "ok"}
    assert await fake_redis.get("run_stats:1") is None


@pytest.mark.anyio
async def test_report_parsing_error_404(fake_db, fake_redis, monkeypatch):
    repo = SimpleNamespace(report_source_error=AsyncMock(return_value=None))
    monkeypatch.setattr(internal_routes, "ParsingRepository", lambda db: repo)

    with pytest.raises(HTTPException) as exc:
        await internal_routes.report_parsing_error(
            1,
            report=ParsingErrorReport(error="boom", is_broken=True),
            run_id=None,
            db=fake_db,
            redis=fake_redis,
            _="internal",
        )
    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_force_run_parser_success_and_publish_failure(fake_db, fake_redis, monkeypatch):
    source = SimpleNamespace(
        id=1,
        url="u",
        site_key="site",
        type="list",
        strategy="deep",
        config={},
    )
    repo = SimpleNamespace(
        get_source_by_id=AsyncMock(return_value=source),
        set_queued=AsyncMock(),
    )
    monkeypatch.setattr(internal_routes, "ParsingRepository", lambda db: repo)
    monkeypatch.setattr(internal_routes, "_sync_hub_from_hub_source", AsyncMock())
    monkeypatch.setattr(internal_routes, "_publish_ops_event", AsyncMock())
    monkeypatch.setattr(internal_routes, "_fetch_rabbit_queue_stats", AsyncMock(return_value={"status": "ok"}))

    monkeypatch.setattr("app.utils.rabbitmq.publish_parsing_task", lambda task: True)
    ok = await internal_routes.force_run_parser(1, strategy=None, db=fake_db, redis=fake_redis, _="internal")
    assert ok["status"] == "ok"

    monkeypatch.setattr("app.utils.rabbitmq.publish_parsing_task", lambda task: False)
    with pytest.raises(HTTPException) as exc:
        await internal_routes.force_run_parser(1, strategy=None, db=fake_db, redis=fake_redis, _="internal")
    assert exc.value.status_code == 500


@pytest.mark.anyio
async def test_force_run_parser_404(fake_db, fake_redis, monkeypatch):
    repo = SimpleNamespace(get_source_by_id=AsyncMock(return_value=None))
    monkeypatch.setattr(internal_routes, "ParsingRepository", lambda db: repo)
    with pytest.raises(HTTPException) as exc:
        await internal_routes.force_run_parser(1, strategy=None, db=fake_db, redis=fake_redis, _="internal")
    assert exc.value.status_code == 404
