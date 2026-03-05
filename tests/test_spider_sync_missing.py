import os

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector

from app.main import app
from app.db import Base, get_db, get_redis
from app.models import ParsingHub, ParsingSource
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
    db_path = tmp_path / "spider_sync_missing.sqlite"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)

    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                ParsingHub.__table__,
                ParsingSource.__table__,
            ],
        )

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        session.bind = engine
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def internal_client(sqlite_db_session):
    async def override_get_db():
        yield sqlite_db_session

    async def override_get_redis():
        # We don't need Redis in this test.
        class Dummy:
            async def get(self, *args, **kwargs):
                return None

        return Dummy()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    # Mock Notification Service to avoid RabbitMQ errors
    class DummyNotifier:
        async def notify(self, *args, **kwargs):
            return None

    app.dependency_overrides[get_notification_service] = lambda: DummyNotifier()

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_sync_spiders_disables_missing_after_grace(internal_client, sqlite_db_session, monkeypatch):
    # Disable grace so missing spiders get disabled immediately for this test.
    monkeypatch.setenv("MISSING_SPIDER_DISABLE_GRACE_MINUTES", "0")

    # Seed DB with a spider that doesn't exist in code.
    ghost_hub = ParsingHub(
        site_key="ghostshop",
        url="https://ghostshop.example/hub",
        strategy="discovery",
        is_active=True,
        status="waiting",
        config={"last_seen_in_code_at": "2000-01-01T00:00:00"},
    )
    sqlite_db_session.add(ghost_hub)

    ghost_source = ParsingSource(
        site_key="ghostshop",
        url="https://ghostshop.example/hub",
        type="hub",
        strategy="discovery",
        is_active=True,
        status="waiting",
        config={"last_seen_in_code_at": "2000-01-01T00:00:00"},
    )
    sqlite_db_session.add(ghost_source)
    await sqlite_db_session.commit()

    from app.config import get_settings

    HEADERS = {"X-Internal-Token": get_settings().internal_api_token}

    # Report only one real spider as available; ghostshop should be disabled.
    resp = internal_client.post(
        "/api/v1/internal/sources/sync-spiders",
        json={"available_spiders": ["detmir"], "default_urls": {"detmir": "https://www.detmir.ru/"}},
        headers=HEADERS,
    )
    assert resp.status_code == 200, resp.text

    await sqlite_db_session.refresh(ghost_hub)
    await sqlite_db_session.refresh(ghost_source)
    assert ghost_source.is_active is False
    assert ghost_source.status == "disabled"
    assert (ghost_hub.config or {}).get("missing_in_code") is True


@pytest.mark.asyncio
async def test_sync_spiders_restores_when_spider_returns(internal_client, sqlite_db_session, monkeypatch):
    # Disable grace so missing spiders get disabled immediately for this test.
    monkeypatch.setenv("MISSING_SPIDER_DISABLE_GRACE_MINUTES", "0")

    # Seed DB with a spider that goes missing and then returns.
    hub = ParsingHub(
        site_key="ghostshop",
        url="https://ghostshop.example/hub",
        strategy="discovery",
        is_active=True,
        status="waiting",
        config={"last_seen_in_code_at": "2000-01-01T00:00:00"},
    )
    sqlite_db_session.add(hub)

    source = ParsingSource(
        site_key="ghostshop",
        url="https://ghostshop.example/hub",
        type="hub",
        strategy="discovery",
        is_active=True,
        status="waiting",
        config={"last_seen_in_code_at": "2000-01-01T00:00:00"},
    )
    sqlite_db_session.add(source)

    list_source = ParsingSource(
        site_key="ghostshop",
        url="https://ghostshop.example/list",
        type="list",
        strategy="deep",
        is_active=True,
        status="waiting",
        category_id=1,
        config={"last_seen_in_code_at": "2000-01-01T00:00:00"},
    )
    sqlite_db_session.add(list_source)
    await sqlite_db_session.commit()

    from app.config import get_settings

    HEADERS = {"X-Internal-Token": get_settings().internal_api_token}

    # First sync: ghostshop not in code => disabled.
    resp1 = internal_client.post(
        "/api/v1/internal/sources/sync-spiders",
        json={"available_spiders": ["detmir"], "default_urls": {"detmir": "https://www.detmir.ru/"}},
        headers=HEADERS,
    )
    assert resp1.status_code == 200, resp1.text
    await sqlite_db_session.refresh(source)
    await sqlite_db_session.refresh(list_source)
    assert source.is_active is False
    assert list_source.is_active is False

    # Second sync: ghostshop is reported as available again => auto-restore.
    resp2 = internal_client.post(
        "/api/v1/internal/sources/sync-spiders",
        json={
            "available_spiders": ["detmir", "ghostshop"],
            "default_urls": {"detmir": "https://www.detmir.ru/", "ghostshop": "https://ghostshop.example/hub"},
        },
        headers=HEADERS,
    )
    assert resp2.status_code == 200, resp2.text

    await sqlite_db_session.refresh(hub)
    await sqlite_db_session.refresh(source)
    await sqlite_db_session.refresh(list_source)
    assert (hub.config or {}).get("missing_in_code") is not True
    assert (source.config or {}).get("missing_in_code") is not True
    # Restored to previous active state.
    assert source.is_active is True
    assert source.status == "waiting"
    assert list_source.is_active is True
    assert list_source.status == "waiting"
