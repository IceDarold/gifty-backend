from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from routes import internal as internal_routes


def _dto(**kwargs):
    now = kwargs.pop("now", datetime(2025, 1, 1, tzinfo=timezone.utc))
    base = {"created_at": now.isoformat(), "updated_at": now.isoformat()}
    base.update(kwargs)
    return base


@pytest.fixture
def frontend_repo(monkeypatch):
    repo = SimpleNamespace(
        list_apps=AsyncMock(return_value=[_dto(id=1, key="a", name="A", is_active=True)]),
        create_app=AsyncMock(return_value=_dto(id=2, key="b", name="B", is_active=True)),
        update_app=AsyncMock(return_value=_dto(id=1, key="a", name="A", is_active=False)),
        delete_app=AsyncMock(return_value=True),
        list_releases=AsyncMock(return_value=[_dto(id=1, app_id=1, version="1", target_url="u", status="draft", health_status="unknown", flags={})]),
        create_release=AsyncMock(return_value=_dto(id=2, app_id=1, version="2", target_url="u2", status="draft", health_status="unknown", flags={})),
        update_release=AsyncMock(return_value=_dto(id=2, app_id=1, version="2", target_url="u2", status="ready", health_status="healthy", flags={})),
        delete_release=AsyncMock(return_value=True),
        _audit=AsyncMock(return_value=True),
        list_profiles=AsyncMock(return_value=[_dto(id=1, key="p", name="P", is_active=True)]),
        create_profile=AsyncMock(return_value=_dto(id=2, key="p2", name="P2", is_active=True)),
        update_profile=AsyncMock(return_value=_dto(id=2, key="p2", name="P2", is_active=False)),
        list_rules=AsyncMock(return_value=[_dto(id=1, profile_id=1, priority=100, host_pattern="*", path_pattern="/*", query_conditions={}, target_release_id=1, flags_override={}, is_active=True)]),
        create_rule=AsyncMock(return_value=_dto(id=2, profile_id=1, priority=100, host_pattern="*", path_pattern="/*", query_conditions={}, target_release_id=1, flags_override={}, is_active=True)),
        update_rule=AsyncMock(return_value=_dto(id=2, profile_id=1, priority=10, host_pattern="x", path_pattern="/*", query_conditions={}, target_release_id=1, flags_override={}, is_active=True)),
        delete_rule=AsyncMock(return_value=True),
        get_runtime_state=AsyncMock(return_value=_dto(id=1, active_profile_id=1, fallback_release_id=1, sticky_enabled=False, sticky_ttl_seconds=60, cache_ttl_seconds=10, updated_by=None, updated_at=datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat())),
        set_runtime_state=AsyncMock(return_value=_dto(id=1, active_profile_id=1, fallback_release_id=1, sticky_enabled=True, sticky_ttl_seconds=60, cache_ttl_seconds=10, updated_by=None, updated_at=datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat())),
        list_allowed_hosts=AsyncMock(return_value=[_dto(id=1, host="example.com", is_active=True)]),
        create_allowed_host=AsyncMock(return_value=_dto(id=2, host="x.com", is_active=True)),
        update_allowed_host=AsyncMock(return_value=_dto(id=2, host="y.com", is_active=False)),
        delete_allowed_host=AsyncMock(return_value=True),
        publish=AsyncMock(return_value=_dto(id=1, active_profile_id=1, fallback_release_id=1, sticky_enabled=False, sticky_ttl_seconds=60, cache_ttl_seconds=10, updated_by=None, updated_at=datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat())),
        rollback=AsyncMock(return_value=_dto(id=1, active_profile_id=1, fallback_release_id=1, sticky_enabled=False, sticky_ttl_seconds=60, cache_ttl_seconds=10, updated_by=None, updated_at=datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat())),
        list_audit_log=AsyncMock(return_value=[_dto(id=1, actor_id=None, action="x", entity_type="y", entity_id="1", before=None, after=None, created_at=datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat())]),
    )

    monkeypatch.setattr(internal_routes, "FrontendRoutingRepository", lambda db: repo, raising=True)
    return repo


@pytest.fixture
def frontend_service(monkeypatch):
    service = SimpleNamespace(
        invalidate_runtime_cache=AsyncMock(return_value=True),
        validate_release=AsyncMock(
            return_value={
                "release_id": 1,
                "ok": True,
                "reason": None,
                "status_code": 200,
                "health_status": "healthy",
                "validated_at": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
            }
        ),
    )
    monkeypatch.setattr(internal_routes, "FrontendRoutingService", lambda db=None, redis=None: service, raising=True)
    return service


@pytest.fixture
def _tg_admin_principal(client):
    client.app.dependency_overrides[internal_routes.verify_internal_token] = lambda: "tg_admin:123"
    return None


@pytest.fixture
def _tg_admin_superadmin(monkeypatch):
    repo = SimpleNamespace(get_subscriber=AsyncMock(return_value=SimpleNamespace(chat_id=123, role="superadmin", permissions=["frontend_release_manager"])))
    monkeypatch.setattr(internal_routes, "TelegramRepository", lambda db: repo, raising=True)
    return None


def test_frontend_apps_crud(client, frontend_repo, _tg_admin_principal, _tg_admin_superadmin):
    resp = client.get("/api/v1/internal/frontend/apps")
    assert resp.status_code == 200

    created = client.post("/api/v1/internal/frontend/apps", json={"key": "b", "name": "B", "is_active": True})
    assert created.status_code == 200

    # 404 branch for update/delete
    frontend_repo.update_app = AsyncMock(return_value=None)
    upd_404 = client.patch("/api/v1/internal/frontend/apps/999", json={"name": "X"})
    assert upd_404.status_code == 404

    frontend_repo.delete_app = AsyncMock(return_value=False)
    del_404 = client.delete("/api/v1/internal/frontend/apps/999")
    assert del_404.status_code == 404


def test_frontend_releases_validate_and_delete(client, frontend_repo, frontend_service, _tg_admin_principal, _tg_admin_superadmin):
    resp = client.get("/api/v1/internal/frontend/releases", params={"app_id": 1})
    assert resp.status_code == 200

    created = client.post(
        "/api/v1/internal/frontend/releases",
        json={"app_id": 1, "version": "1", "target_url": "u", "status": "draft", "health_status": "unknown", "flags": {}},
    )
    assert created.status_code == 200

    validated = client.post("/api/v1/internal/frontend/releases/1/validate")
    assert validated.status_code == 200
    assert frontend_repo._audit.await_count >= 1

    deleted = client.delete("/api/v1/internal/frontend/releases/1")
    assert deleted.status_code == 200
    assert frontend_service.invalidate_runtime_cache.await_count >= 1

    # validate 404 branch
    frontend_service.validate_release = AsyncMock(side_effect=ValueError("release not found"))
    missing = client.post("/api/v1/internal/frontend/releases/999/validate")
    assert missing.status_code == 404


def test_frontend_profiles_rules_runtime_hosts_publish_rollback_audit(
    client, frontend_repo, frontend_service, _tg_admin_principal, _tg_admin_superadmin
):
    assert client.get("/api/v1/internal/frontend/profiles").status_code == 200
    assert client.post("/api/v1/internal/frontend/profiles", json={"key": "p2", "name": "P2", "is_active": True}).status_code == 200

    assert client.get("/api/v1/internal/frontend/rules").status_code == 200
    assert (
        client.post(
            "/api/v1/internal/frontend/rules",
            json={"profile_id": 1, "priority": 100, "host_pattern": "*", "path_pattern": "/*", "query_conditions": {}, "target_release_id": 1, "flags_override": {}, "is_active": True},
        ).status_code
        == 200
    )

    assert client.get("/api/v1/internal/frontend/runtime-state").status_code == 200
    assert client.patch("/api/v1/internal/frontend/runtime-state", json={"sticky_enabled": True}).status_code == 200

    assert client.get("/api/v1/internal/frontend/allowed-hosts").status_code == 200
    assert client.post("/api/v1/internal/frontend/allowed-hosts", json={"host": "x.com", "is_active": True}).status_code == 200
    assert client.patch("/api/v1/internal/frontend/allowed-hosts/2", json={"host": "y.com"}).status_code == 200
    assert client.delete("/api/v1/internal/frontend/allowed-hosts/2").status_code == 200

    assert client.post("/api/v1/internal/frontend/publish", json={"active_profile_id": 1, "fallback_release_id": 1}).status_code == 200

    frontend_repo.rollback = AsyncMock(return_value=None)
    bad = client.post("/api/v1/internal/frontend/rollback", json={})
    assert bad.status_code == 400

    assert client.get("/api/v1/internal/frontend/audit-log").status_code == 200


def test_frontend_profiles_rules_runtime_state_404_branches(client, frontend_repo, _tg_admin_principal, _tg_admin_superadmin):
    frontend_repo.update_profile = AsyncMock(return_value=None)
    resp = client.patch("/api/v1/internal/frontend/profiles/999", json={"name": "X"})
    assert resp.status_code == 404

    frontend_repo.update_rule = AsyncMock(return_value=None)
    resp2 = client.patch("/api/v1/internal/frontend/rules/999", json={"priority": 1})
    assert resp2.status_code == 404

    frontend_repo.delete_rule = AsyncMock(return_value=False)
    resp3 = client.delete("/api/v1/internal/frontend/rules/999")
    assert resp3.status_code == 404

    frontend_repo.get_runtime_state = AsyncMock(return_value=None)
    resp4 = client.get("/api/v1/internal/frontend/runtime-state")
    assert resp4.status_code == 404
