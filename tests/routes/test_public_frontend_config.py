from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.public import router, get_db, get_redis


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


def test_public_frontend_config_sets_cookie_and_cache_headers(monkeypatch):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = _db_override
    app.dependency_overrides[get_redis] = _redis_override

    from app.services.frontend_routing import FrontendRoutingService

    monkeypatch.setattr(
        FrontendRoutingService,
        "resolve_config",
        AsyncMock(
            return_value={
                "target_url": "https://product.vercel.app/product",
                "release_id": 55,
                "cache_ttl": 15,
                "sticky_key": "fr_55",
                "flags": {"maintenance": False},
                "sticky_enabled": True,
                "sticky_ttl_seconds": 1800,
            }
        ),
    )

    client = TestClient(app)
    response = client.get("/api/v1/public/frontend-config", params={"host": "giftyai.ru", "path": "/product"})

    assert response.status_code == 200
    assert response.json()["release_id"] == 55
    assert response.headers["cache-control"] == "public, max-age=15"
    assert "gifty_frontend_release=55" in response.headers.get("set-cookie", "")
