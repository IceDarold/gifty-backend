from __future__ import annotations

import pytest

from app.repositories.catalog import CatalogRepository


class _DummyCatalogRepo(CatalogRepository):
    async def upsert_products(self, products: list[dict]) -> int:
        return await CatalogRepository.upsert_products(self, products)  # type: ignore[misc]

    async def get_active_products_count(self) -> int:
        return await CatalogRepository.get_active_products_count(self)  # type: ignore[misc]

    async def get_products_without_embeddings(self, model_version: str, limit: int = 100):
        return await CatalogRepository.get_products_without_embeddings(self, model_version, limit)  # type: ignore[misc]

    async def save_embeddings(self, embeddings: list[dict]) -> int:
        return await CatalogRepository.save_embeddings(self, embeddings)  # type: ignore[misc]

    async def mark_inactive_except(self, seen_ids: set[str]) -> int:
        return await CatalogRepository.mark_inactive_except(self, seen_ids)  # type: ignore[misc]

    async def delete_products_by_site(self, site_key: str) -> int:
        return await CatalogRepository.delete_products_by_site(self, site_key)  # type: ignore[misc]

    async def get_products(self, limit: int = 50, offset: int = 0, is_active=None, merchant=None, category=None, search=None):
        return await CatalogRepository.get_products(self, limit, offset, is_active, merchant, category, search)  # type: ignore[misc]

    async def count_products(self, is_active=None, merchant=None, category=None, search=None) -> int:
        return await CatalogRepository.count_products(self, is_active, merchant, category, search)  # type: ignore[misc]


@pytest.mark.anyio
async def test_catalog_repository_abstract_pass_methods_are_executable():
    repo = _DummyCatalogRepo()
    assert await repo.upsert_products([]) is None
    assert await repo.get_active_products_count() is None
    assert await repo.get_products_without_embeddings("v") is None
    assert await repo.save_embeddings([]) is None
    assert await repo.mark_inactive_except(set()) is None
    assert await repo.delete_products_by_site("s") is None
    assert await repo.get_products() is None
    assert await repo.count_products() is None

