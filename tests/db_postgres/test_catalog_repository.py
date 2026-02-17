from __future__ import annotations

import os
import uuid
import pytest
from sqlalchemy import select

from app.models import Product, ProductEmbedding
from app.repositories.catalog import PostgresCatalogRepository

pytestmark = pytest.mark.skipif(
    os.getenv("DATABASE_URL", "").startswith("sqlite"),
    reason="Catalog repository tests require PostgreSQL (on_conflict, pgvector)"
)


def _product(gift_id: str, title: str, is_active: bool = True):
    return {
        "gift_id": gift_id,
        "title": title,
        "product_url": f"https://example.com/{gift_id}",
        "is_active": is_active,
        "content_hash": f"hash-{gift_id}",
    }


def _embedding(gift_id: str, model_name: str, model_version: str):
    return {
        "gift_id": gift_id,
        "model_name": model_name,
        "model_version": model_version,
        "dim": 1024,
        "embedding": [0.01] * 1024,
        "content_hash": f"hash-{gift_id}",
    }


@pytest.mark.asyncio
async def test_upsert_products_and_count(postgres_session):
    repo = PostgresCatalogRepository(postgres_session)

    inserted = await repo.upsert_products([
        _product("p1", "Prod 1"),
        _product("p2", "Prod 2"),
    ])
    assert inserted == 2

    # Update existing
    inserted_again = await repo.upsert_products([
        _product("p1", "Prod 1 updated"),
        _product("p3", "Prod 3"),
    ])
    assert inserted_again == 1

    count = await repo.get_active_products_count()
    assert count == 3


@pytest.mark.asyncio
async def test_mark_inactive_except(postgres_session):
    repo = PostgresCatalogRepository(postgres_session)

    await repo.upsert_products([
        _product("p10", "Prod 10"),
        _product("p11", "Prod 11"),
    ])

    updated = await repo.mark_inactive_except({"p10"})
    assert updated == 1

    result = await postgres_session.execute(
        select(Product).where(Product.gift_id == "p11")
    )
    p11 = result.scalar_one()
    assert p11.is_active is False


@pytest.mark.asyncio
async def test_embeddings_flow(postgres_session):
    repo = PostgresCatalogRepository(postgres_session)

    await repo.upsert_products([
        _product("p20", "Prod 20"),
        _product("p21", "Prod 21"),
    ])

    missing = await repo.get_products_without_embeddings("v1")
    assert {p.gift_id for p in missing} >= {"p20", "p21"}

    saved = await repo.save_embeddings([
        _embedding("p20", "test-model", "v1"),
        _embedding("p21", "test-model", "v1"),
    ])
    assert saved >= 2

    missing_after = await repo.get_products_without_embeddings("v1")
    assert "p20" not in {p.gift_id for p in missing_after}


@pytest.mark.asyncio
async def test_search_similar_products(postgres_session, monkeypatch):
    repo = PostgresCatalogRepository(postgres_session)

    await repo.upsert_products([
        _product("p30", "Prod 30"),
    ])

    await repo.save_embeddings([
        _embedding("p30", "test-model", "v1"),
    ])

    products = await repo.search_similar_products(
        embedding=[0.01] * 1024,
        limit=5,
        model_name="test-model",
    )
    assert products
    assert products[0].gift_id == "p30"


@pytest.mark.asyncio
async def test_llm_scores_flow(postgres_session):
    repo = PostgresCatalogRepository(postgres_session)

    await repo.upsert_products([
        _product("p40", "Prod 40"),
        _product("p41", "Prod 41"),
    ])

    missing = await repo.get_products_without_llm_score(limit=10)
    assert {p.gift_id for p in missing} >= {"p40", "p41"}

    updated = await repo.save_llm_scores([
        {
            "gift_id": "p40",
            "llm_gift_score": 0.9,
            "llm_gift_reasoning": "ok",
        }
    ])
    assert updated >= 1

    missing_after = await repo.get_products_without_llm_score(limit=10)
    assert "p40" not in {p.gift_id for p in missing_after}
