from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.repositories.catalog import PostgresCatalogRepository


class _FakeScalars:
    def __init__(self, items):
        self._items = items

    def all(self):
        return list(self._items)


class _FakeResult:
    def __init__(self, *, scalars_items=None, scalar_value=None, rowcount=0):
        self._scalars_items = scalars_items
        self._scalar_value = scalar_value
        self.rowcount = rowcount

    def scalars(self):
        return _FakeScalars(self._scalars_items or [])

    def scalar(self):
        return self._scalar_value


@pytest.mark.anyio
async def test_upsert_products_empty_returns_zero():
    repo = PostgresCatalogRepository(session=AsyncMock())
    assert await repo.upsert_products([]) == 0


@pytest.mark.anyio
async def test_upsert_products_non_postgres_fallback_rowcount(monkeypatch):
    session = AsyncMock()
    session.bind = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))
    session.execute = AsyncMock(return_value=_FakeResult(rowcount=5))
    repo = PostgresCatalogRepository(session=session)

    out = await repo.upsert_products(
        [
            {"product_id": "s:1", "title": "T", "product_url": "u", "merchant": "s", "is_active": True},
        ]
    )
    assert out == 5


@pytest.mark.anyio
async def test_upsert_products_postgres_counts_inserts_via_xmax():
    session = AsyncMock()
    session.bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
    session.execute = AsyncMock(return_value=_FakeResult(scalars_items=[0, 1, 0]))
    repo = PostgresCatalogRepository(session=session)

    out = await repo.upsert_products(
        [
            {"product_id": "s:1", "title": "T", "product_url": "u", "merchant": "s", "is_active": True},
            {"product_id": "s:2", "title": "T2", "product_url": "u2", "merchant": "s", "is_active": True},
            {"product_id": "s:3", "title": "T3", "product_url": "u3", "merchant": "s", "is_active": True},
        ]
    )
    assert out == 2


@pytest.mark.anyio
async def test_mark_inactive_except_requires_ids():
    session = AsyncMock()
    repo = PostgresCatalogRepository(session=session)
    assert await repo.mark_inactive_except(set()) == 0


@pytest.mark.anyio
async def test_mark_inactive_except_returns_rowcount():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_FakeResult(rowcount=4))
    repo = PostgresCatalogRepository(session=session)
    assert await repo.mark_inactive_except({"s:1"}) == 4


@pytest.mark.anyio
async def test_save_embeddings_logs_and_reraises(monkeypatch):
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=RuntimeError("db down"))
    repo = PostgresCatalogRepository(session=session)

    with pytest.raises(RuntimeError):
        await repo.save_embeddings([{"product_id": "s:1", "embedding": [0.0], "model_name": "m", "model_version": "v"}])


@pytest.mark.anyio
async def test_save_embeddings_empty_returns_zero():
    repo = PostgresCatalogRepository(session=AsyncMock())
    assert await repo.save_embeddings([]) == 0


@pytest.mark.anyio
async def test_delete_products_by_site_executes_delete():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_FakeResult(rowcount=3))
    repo = PostgresCatalogRepository(session=session)
    assert await repo.delete_products_by_site("s") == 3


@pytest.mark.anyio
async def test_search_similar_products_returns_empty_in_dev_on_error(monkeypatch):
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=RuntimeError("boom"))
    repo = PostgresCatalogRepository(session=session)

    monkeypatch.setattr("app.services.notifications.get_notification_service", lambda: AsyncMock(notify=AsyncMock()))
    monkeypatch.setattr("app.config.get_settings", lambda: SimpleNamespace(env="dev"))

    products = await repo.search_similar_products(embedding=[0.1, 0.2], limit=3, min_similarity=0.0)
    assert products == []


@pytest.mark.anyio
async def test_search_similar_products_reraises_in_prod(monkeypatch):
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=RuntimeError("boom"))
    repo = PostgresCatalogRepository(session=session)

    monkeypatch.setattr("app.services.notifications.get_notification_service", lambda: None)
    monkeypatch.setattr("app.config.get_settings", lambda: SimpleNamespace(env="prod"))

    with pytest.raises(RuntimeError):
        await repo.search_similar_products(embedding=[0.1, 0.2], limit=3, min_similarity=0.0)


@pytest.mark.anyio
async def test_search_similar_products_applies_optional_filters():
    session = AsyncMock()
    session.bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
    session.execute = AsyncMock(return_value=_FakeResult(scalars_items=[SimpleNamespace(product_id="s:1")]))
    repo = PostgresCatalogRepository(session=session)

    out = await repo.search_similar_products(
        embedding=[0.1, 0.2],
        limit=1,
        min_similarity=0.5,
        is_active_only=True,
        max_price=100,
        max_delivery_days=7,
        model_name="m",
    )
    assert out[0].product_id == "s:1"


@pytest.mark.anyio
async def test_get_products_and_count_products_apply_filters():
    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[
            _FakeResult(scalars_items=[SimpleNamespace(product_id="s:1")]),
            _FakeResult(scalar_value=7),
        ]
    )
    repo = PostgresCatalogRepository(session=session)

    out = await repo.get_products(limit=1, offset=0, is_active=True, merchant="m", category="c", search="q")
    assert out[0].product_id == "s:1"

    count = await repo.count_products(is_active=True, merchant="m", category="c", search="q")
    assert count == 7
