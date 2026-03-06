from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.schemas.parsing import ScrapedCategory, ScrapedProduct
from app.services import ingestion as ingestion_module


def test_normalize_url_strips_tracking_params():
    url = "https://example.com/p?utm_source=x&a=1#frag"
    assert ingestion_module.normalize_url(url) == "https://example.com/p?a=1"


def test_normalize_url_on_exception_returns_original(monkeypatch):
    monkeypatch.setattr(ingestion_module, "urlparse", lambda url: (_ for _ in ()).throw(RuntimeError("boom")))
    assert ingestion_module.normalize_url("x") == "x"


@pytest.mark.anyio
async def test_ingest_products_dedup_skips_missing_site_key_and_links_categories(monkeypatch):
    db = AsyncMock()
    db.commit = AsyncMock()

    catalog_repo = SimpleNamespace(upsert_products=AsyncMock(return_value=2))
    source = SimpleNamespace(
        id=1,
        site_key="site",
        type="list",
        category_id=99,
        config={"strip_params": ["x"]},
    )
    parsing_repo = SimpleNamespace(
        get_source=AsyncMock(return_value=source),
        get_or_create_category_maps=AsyncMock(),
        get_or_create_merchant=AsyncMock(return_value=SimpleNamespace(name="Shop")),
        upsert_product_category_links=AsyncMock(),
        update_source_stats=AsyncMock(),
        log_parsing_run=AsyncMock(),
    )

    monkeypatch.setattr(ingestion_module, "PostgresCatalogRepository", lambda db: catalog_repo)
    monkeypatch.setattr(ingestion_module, "ParsingRepository", lambda db, redis=None: parsing_repo)

    svc = ingestion_module.IngestionService(db)

    products = [
        ScrapedProduct(title="t1", product_url="https://p?x=1", site_key=""),
        ScrapedProduct(title="t1", product_url="https://p?x=1", site_key="site"),
        ScrapedProduct(title="t1", product_url="https://p?x=1", site_key="site"),  # dup
    ]

    out = await svc.ingest_products(products, source_id=1, run_id=7)
    assert out == 2
    parsing_repo.upsert_product_category_links.assert_awaited()
    parsing_repo.update_source_stats.assert_awaited()


@pytest.mark.anyio
async def test_ingest_products_empty_returns_zero(monkeypatch):
    db = AsyncMock()
    monkeypatch.setattr(ingestion_module, "PostgresCatalogRepository", lambda db: SimpleNamespace(upsert_products=AsyncMock()))
    monkeypatch.setattr(ingestion_module, "ParsingRepository", lambda db, redis=None: SimpleNamespace(get_source=AsyncMock()))
    svc = ingestion_module.IngestionService(db)
    assert await svc.ingest_products([], source_id=1) == 0


@pytest.mark.anyio
async def test_ingest_categories_promotes_with_quota_and_tolerates_errors(monkeypatch):
    db = AsyncMock()
    db.commit = AsyncMock()

    disc1 = SimpleNamespace(id=1, state="new", promoted_source_id=None)
    disc2 = SimpleNamespace(id=2, state="new", promoted_source_id=None)
    parsing_repo = SimpleNamespace(
        count_discovered_today=AsyncMock(return_value=0),
        get_source_by_url=AsyncMock(return_value=None),
        get_or_create_discovered_category=AsyncMock(side_effect=[disc1, disc2]),
        upsert_source=AsyncMock(side_effect=[SimpleNamespace(id=10), RuntimeError("boom")]),
    )
    monkeypatch.setattr(ingestion_module, "PostgresCatalogRepository", lambda db: SimpleNamespace(upsert_products=AsyncMock()))
    monkeypatch.setattr(ingestion_module, "ParsingRepository", lambda db, redis=None: parsing_repo)

    svc = ingestion_module.IngestionService(db)
    cats = [
        ScrapedCategory(name="c1", url="https://s/c1", parent_url=None, site_key="s"),
        ScrapedCategory(name="c2", url="https://s/c2", parent_url=None, site_key="s"),
    ]
    out = await svc.ingest_categories(cats, activation_quota=1)
    assert out == 1  # only one upsert succeeded
    assert disc1.state == "promoted"
    assert disc1.promoted_source_id == 10


@pytest.mark.anyio
async def test_ingest_categories_empty_returns_zero(monkeypatch):
    db = AsyncMock()
    monkeypatch.setattr(ingestion_module, "PostgresCatalogRepository", lambda db: SimpleNamespace(upsert_products=AsyncMock()))
    monkeypatch.setattr(ingestion_module, "ParsingRepository", lambda db, redis=None: SimpleNamespace(count_promoted_categories_today=AsyncMock()))
    svc = ingestion_module.IngestionService(db)
    assert await svc.ingest_categories([]) == 0
