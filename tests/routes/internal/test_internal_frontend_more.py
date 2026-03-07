from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from routes import internal as internal_routes


@pytest.fixture
def _tg_admin_principal(client):
    client.app.dependency_overrides[internal_routes.verify_internal_token] = lambda: "tg_admin:555"
    return None


@pytest.fixture
def _tg_admin_reader_only(monkeypatch):
    repo = SimpleNamespace(get_subscriber=AsyncMock(return_value=SimpleNamespace(chat_id=555, role="admin", permissions=[])))
    monkeypatch.setattr(internal_routes, "TelegramRepository", lambda db: repo, raising=True)
    return None


@pytest.fixture
def _tg_admin_manager(monkeypatch):
    repo = SimpleNamespace(
        get_subscriber=AsyncMock(
            return_value=SimpleNamespace(chat_id=555, role="admin", permissions=["frontend_release_manager"])
        )
    )
    monkeypatch.setattr(internal_routes, "TelegramRepository", lambda db: repo, raising=True)
    return None


def test_require_frontend_reader_insufficient_role_403(client, _tg_admin_principal, monkeypatch):
    repo = SimpleNamespace(get_subscriber=AsyncMock(return_value=SimpleNamespace(chat_id=555, role="user", permissions=[])))
    monkeypatch.setattr(internal_routes, "TelegramRepository", lambda db: repo, raising=True)

    resp = client.get("/api/v1/internal/frontend/apps")
    assert resp.status_code == 403


def test_update_and_delete_frontend_app_success_paths(client, _tg_admin_principal, _tg_admin_manager, monkeypatch):
    repo = SimpleNamespace(
        list_apps=AsyncMock(return_value=[]),
        update_app=AsyncMock(return_value={"id": 1, "key": "a", "name": "A", "is_active": True, "created_at": "2025-01-01T00:00:00Z", "updated_at": "2025-01-01T00:00:00Z"}),
        delete_app=AsyncMock(return_value=True),
    )
    monkeypatch.setattr(internal_routes, "FrontendRoutingRepository", lambda db: repo, raising=True)

    ok_upd = client.patch("/api/v1/internal/frontend/apps/1", json={"name": "A"})
    assert ok_upd.status_code == 200

    ok_del = client.delete("/api/v1/internal/frontend/apps/1")
    assert ok_del.status_code == 200


def test_update_release_success_and_404_branches(client, _tg_admin_principal, _tg_admin_manager, monkeypatch):
    repo = SimpleNamespace(
        update_release=AsyncMock(return_value={"id": 2, "app_id": 1, "version": "2", "target_url": "u2", "status": "ready", "health_status": "healthy", "flags": {}, "created_at": "2025-01-01T00:00:00Z", "updated_at": "2025-01-01T00:00:00Z"}),
    )
    monkeypatch.setattr(internal_routes, "FrontendRoutingRepository", lambda db: repo, raising=True)

    ok = client.patch("/api/v1/internal/frontend/releases/2", json={"status": "ready"})
    assert ok.status_code == 200

    repo.update_release = AsyncMock(return_value=None)
    missing = client.patch("/api/v1/internal/frontend/releases/999", json={"status": "ready"})
    assert missing.status_code == 404


def test_delete_release_404_branch(client, _tg_admin_principal, _tg_admin_manager, monkeypatch):
    repo = SimpleNamespace(delete_release=AsyncMock(return_value=False))
    service = SimpleNamespace(invalidate_runtime_cache=AsyncMock(return_value=True))
    monkeypatch.setattr(internal_routes, "FrontendRoutingRepository", lambda db: repo, raising=True)
    monkeypatch.setattr(internal_routes, "FrontendRoutingService", lambda db=None, redis=None: service, raising=True)

    resp = client.delete("/api/v1/internal/frontend/releases/123")
    assert resp.status_code == 404


def test_allowed_hosts_404_branches(client, _tg_admin_principal, _tg_admin_manager, monkeypatch):
    repo = SimpleNamespace(
        update_allowed_host=AsyncMock(return_value=None),
        delete_allowed_host=AsyncMock(return_value=False),
    )
    monkeypatch.setattr(internal_routes, "FrontendRoutingRepository", lambda db: repo, raising=True)

    upd = client.patch("/api/v1/internal/frontend/allowed-hosts/1", json={"host": "x.com"})
    assert upd.status_code == 404

    deleted = client.delete("/api/v1/internal/frontend/allowed-hosts/1")
    assert deleted.status_code == 404


def test_frontend_rollback_success_invalidates_cache(client, _tg_admin_principal, _tg_admin_manager, monkeypatch):
    repo = SimpleNamespace(rollback=AsyncMock(return_value={"id": 1, "active_profile_id": 1, "fallback_release_id": 1, "sticky_enabled": False, "sticky_ttl_seconds": 60, "cache_ttl_seconds": 10, "updated_by": None, "updated_at": "2025-01-01T00:00:00Z"}))
    service = SimpleNamespace(invalidate_runtime_cache=AsyncMock(return_value=True))
    monkeypatch.setattr(internal_routes, "FrontendRoutingRepository", lambda db: repo, raising=True)
    monkeypatch.setattr(internal_routes, "FrontendRoutingService", lambda db=None, redis=None: service, raising=True)

    resp = client.post("/api/v1/internal/frontend/rollback", json={"app_id": 1})
    assert resp.status_code == 200
    assert service.invalidate_runtime_cache.await_count >= 1
