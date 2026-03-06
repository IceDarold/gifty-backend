from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.public import router, get_db, get_redis, get_notification_service


@pytest.fixture
def db_mock():
    mock = AsyncMock()
    mock.add = MagicMock()
    mock.commit = AsyncMock()
    return mock


@pytest.fixture
def redis_mock():
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.incr = AsyncMock(return_value=1)
    mock.expire = AsyncMock()
    return mock


@pytest.fixture
def notifications_mock():
    return AsyncMock()


@pytest.fixture
def client(db_mock, redis_mock, notifications_mock, monkeypatch):
    app = FastAPI()
    app.include_router(router)

    app.dependency_overrides[get_db] = lambda: db_mock
    app.dependency_overrides[get_redis] = lambda: redis_mock
    app.dependency_overrides[get_notification_service] = lambda: notifications_mock

    # Avoid real FrontendRoutingService logic.
    resolved = {
        "target_url": "https://example.com",
        "release_id": 1,
        "cache_ttl": 10,
        "sticky_key": "k",
        "flags": {},
        "sticky_enabled": True,
        "sticky_ttl_seconds": 60,
    }

    class _Svc:
        STICKY_COOKIE_NAME = "sticky_release"

        def __init__(self, db=None, redis=None):
            self.db = db
            self.redis = redis

        async def resolve_config(self, req):
            return dict(resolved)

    monkeypatch.setattr("routes.public.FrontendRoutingService", _Svc, raising=True)
    return TestClient(app)


def test_public_team_returns_rows(client, db_mock):
    result = MagicMock()
    result.scalars.return_value.all.return_value = [
        {
            "id": "00000000-0000-0000-0000-000000000001",
            "slug": "s",
            "name": "N",
            "role": "R",
            "bio": None,
            "linkedin_url": None,
            "photo_public_id": None,
            "sort_order": 1,
        }
    ]
    db_mock.execute = AsyncMock(return_value=result)

    resp = client.get("/api/v1/public/team")
    assert resp.status_code == 200


def test_newsletter_subscribe_honeypot_and_notify(client, notifications_mock):
    hp = client.post("/api/v1/public/newsletter-subscribe", json={"email": "a@b.com", "hp": "x"})
    assert hp.status_code == 201
    notifications_mock.notify.assert_not_called()

    ok = client.post("/api/v1/public/newsletter-subscribe", json={"email": "a@b.com", "hp": ""})
    assert ok.status_code == 201
    notifications_mock.notify.assert_called()


def test_public_frontend_config_parses_sticky_cookie(client):
    resp = client.get("/api/v1/public/frontend-config", headers={"host": "example.com"}, cookies={"sticky_release": "123"})
    assert resp.status_code == 200
    assert resp.cookies.get("sticky_release") == "1"
