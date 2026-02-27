from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.internal import router, get_db, get_redis


def _db_override():
    yield object()


async def _redis_override():
    class DummyRedis:
        async def get(self, key):
            return None

        async def setex(self, key, ttl, value):
            return None

        async def scan(self, cursor=0, match=None, count=100):
            return 0, []

        async def delete(self, *keys):
            return 0

    return DummyRedis()


def _app_with_overrides():
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = _db_override
    app.dependency_overrides[get_redis] = _redis_override
    return app


def test_mutation_requires_frontend_manager_permission(monkeypatch):
    app = _app_with_overrides()

    from routes import internal as internal_routes
    from app.repositories.telegram import TelegramRepository

    app.dependency_overrides[internal_routes.verify_internal_token] = lambda: "tg_admin:123"
    monkeypatch.setattr(TelegramRepository, "get_subscriber", AsyncMock(return_value=SimpleNamespace(role="admin", permissions=[])))

    client = TestClient(app)
    response = client.post(
        "/api/v1/internal/frontend/publish",
        json={"active_profile_id": 1, "fallback_release_id": 1},
        headers={"X-Internal-Token": "dummy"},
    )

    assert response.status_code == 403


def test_publish_ok_for_superadmin(monkeypatch):
    app = _app_with_overrides()

    from routes import internal as internal_routes
    from app.repositories.telegram import TelegramRepository
    from app.repositories.frontend_routing import FrontendRoutingRepository
    from app.services.frontend_routing import FrontendRoutingService

    app.dependency_overrides[internal_routes.verify_internal_token] = lambda: "tg_admin:123"
    monkeypatch.setattr(TelegramRepository, "get_subscriber", AsyncMock(return_value=SimpleNamespace(role="superadmin", permissions=[])))
    monkeypatch.setattr(
        FrontendRoutingRepository,
        "publish",
        AsyncMock(
            return_value=SimpleNamespace(
                id=1,
                active_profile_id=1,
                fallback_release_id=2,
                sticky_enabled=True,
                sticky_ttl_seconds=1800,
                cache_ttl_seconds=15,
                updated_by=123,
                updated_at="2026-02-23T00:00:00Z",
            )
        ),
    )
    monkeypatch.setattr(FrontendRoutingService, "invalidate_runtime_cache", AsyncMock(return_value=None))

    client = TestClient(app)
    response = client.post(
        "/api/v1/internal/frontend/publish",
        json={"active_profile_id": 1, "fallback_release_id": 2},
        headers={"X-Internal-Token": "dummy"},
    )

    assert response.status_code == 200
    assert response.json()["fallback_release_id"] == 2
