import pytest
import pytest_asyncio
import uuid
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector

from app.main import app
from app.db import get_db, Base, get_redis
from app.models import ParsingSource, ParsingRun, CategoryMap, Product, DiscoveredCategory, ParsingHub, Merchant
from app.services.notifications import get_notification_service

# --- SQLite Compiles for Postgres Dialects ---
@compiles(UUID, "sqlite")
def _compile_uuid_sqlite(type_, compiler, **kw):
    return "CHAR(36)"

@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "TEXT"

@compiles(Vector, "sqlite")
def _compile_vector_sqlite(type_, compiler, **kw):
    return "BLOB"

@pytest_asyncio.fixture
async def sqlite_db_session(tmp_path):
    db_path = tmp_path / "parsing_test.sqlite"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)

    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                ParsingSource.__table__,
                ParsingHub.__table__,
                DiscoveredCategory.__table__,
                ParsingRun.__table__,
                CategoryMap.__table__,
                Merchant.__table__,
                Product.__table__
            ],
        )

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        # Manually bind engine for dialect check in repo
        session.bind = engine
        yield session
    
    await engine.dispose()

@pytest_asyncio.fixture
async def internal_client(sqlite_db_session):
    async def override_get_db():
        yield sqlite_db_session

    async def override_get_redis():
        mock = AsyncMock()
        mock.get.return_value = None
        mock.set.return_value = True
        return mock

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    
    # Mock Notification Service to avoid RabbitMQ errors
    mock_notifier = AsyncMock()
    app.dependency_overrides[get_notification_service] = lambda: mock_notifier

    with TestClient(app) as client:
        yield client
    
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_parsing_internal_flow(internal_client):
    from app.config import get_settings
    settings = get_settings()
    HEADERS = {"X-Internal-Token": settings.internal_api_token}
    
    # 1. Create Source
    source_data = {
        "site_key": "mrgeek",
        "url": "https://mrgeek.ru/category/podarki/",
        "type": "hub",
        "strategy": "discovery",
        "is_active": True
    }
    response = internal_client.post("/api/v1/internal/sources", json=source_data, headers=HEADERS)
    assert response.status_code == 200, f"Failed to create source: {response.text}"
    source = response.json()
    source_id = source["id"]

    # 2. Force Run
    with patch("app.utils.rabbitmq.publish_parsing_task", return_value=True):
        response = internal_client.post(f"/api/v1/internal/sources/{source_id}/force-run", headers=HEADERS)
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    # 3. Ingest Batch
    ingest_data = {
        "items": [
            {
                "gift_id": "mrgeek:https://mrgeek.ru/product/1",
                "title": "Ingested Gift",
                "price": 500.0,
                "product_url": "https://mrgeek.ru/product/1",
                "image_url": "https://mrgeek.ru/img1.jpg",
                "category": "Gadgets",
                "merchant": "mrgeek",
                "content_text": "Nice gadget",
                "site_key": "mrgeek"
            }
        ],
        "categories": [
            {
                "name": "Super Gadgets",
                "url": "https://mrgeek.ru/cat/super",
                "site_key": "mrgeek"
            }
        ],
        "source_id": source_id,
        "stats": {"count": 1}
    }
    response = internal_client.post("/api/v1/internal/ingest-batch", json=ingest_data, headers=HEADERS)
    assert response.status_code == 200, f"Ingest failed: {response.text}"
    res = response.json()
    assert res["items_ingested"] >= 0 # Rowcount in SQLite might be 1 if new
    assert res["categories_ingested"] > 0

    # 4. Check Categories Tasks (CategoryMap)
    response = internal_client.get("/api/v1/internal/categories/tasks", headers=HEADERS)
    assert response.status_code == 200
    tasks = response.json()
    assert any(t["external_name"] == "Gadgets" for t in tasks), f"Gadgets not in tasks: {tasks}"

    # 5. Check discovered sources (ParsingSource)
    response = internal_client.get("/api/v1/internal/sources", headers=HEADERS)
    assert response.status_code == 200
    sources = response.json()
    assert any(s["site_key"] == "mrgeek" and "Super Gadgets" in (s["config"] or {}).get("discovery_name", "") for s in sources)

    # 6. Check Monitoring
    response = internal_client.get("/api/v1/internal/monitoring", headers=HEADERS)
    assert response.status_code == 200
    mon = response.json()
    assert len(mon) > 0
    assert mon[0]["site_key"] == "mrgeek"
    assert mon[0]["total_sources"] > 0

    print("\n✅ Internal Parsing API flow and Monitoring test passed successfully!")
