from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import routes as auth_module
from app.utils.errors import install_exception_handlers


@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(auth_module.router)
    install_exception_handlers(app)

    fake_redis = AsyncMock()

    async def override_get_redis():
        return fake_redis

    async def override_get_db():
        yield AsyncMock()

    app.dependency_overrides[auth_module.get_redis] = override_get_redis
    app.dependency_overrides[auth_module.get_db] = override_get_db

    # Keep providers deterministic
    monkeypatch.setattr(auth_module, "get_provider_config", lambda provider, settings: SimpleNamespace(name=provider))
    monkeypatch.setattr(auth_module, "build_authorize_url", lambda config, redirect_uri, state, code_challenge: f"https://auth/{config.name}?state={state}")

    return TestClient(app)


def test_safe_return_to_blocks_external_hosts():
    assert auth_module._safe_return_to("https://evil.example/x") == "/"


def test_safe_return_to_allows_frontend_host():
    # reuse frontend_base host
    base = str(auth_module.settings.frontend_base).rstrip("/")
    assert auth_module._safe_return_to(f"{base}/a?b=1#c") == "/a?b=1#c"


def test_oauth_start_redirects_and_saves_state(client, monkeypatch):
    save_state = AsyncMock()
    monkeypatch.setattr(auth_module.state_store, "save_state", save_state)
    monkeypatch.setattr(auth_module, "generate_state", lambda: "st")
    monkeypatch.setattr(auth_module.pkce, "generate_code_verifier", lambda: "ver")
    monkeypatch.setattr(auth_module.pkce, "generate_code_challenge", lambda verifier: "chl")

    resp = client.get("/api/v1/auth/google/start?return_to=/x", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"].startswith("https://auth/google?state=st")
    assert save_state.await_count == 1


def test_oauth_callback_requires_code_and_state(client):
    resp = client.get("/api/v1/auth/google/callback")
    assert resp.status_code == 400


def test_oauth_callback_state_missing(client, monkeypatch):
    monkeypatch.setattr(auth_module.state_store, "pop_state", AsyncMock(return_value=None))
    resp = client.get("/api/v1/auth/google/callback?code=c&state=s")
    assert resp.status_code == 400


def test_oauth_callback_provider_mismatch(client, monkeypatch):
    monkeypatch.setattr(auth_module.state_store, "pop_state", AsyncMock(return_value={"provider": "yandex"}))
    resp = client.get("/api/v1/auth/google/callback?code=c&state=s")
    assert resp.status_code == 400


def test_oauth_callback_missing_verifier(client, monkeypatch):
    monkeypatch.setattr(auth_module.state_store, "pop_state", AsyncMock(return_value={"provider": "google"}))
    resp = client.get("/api/v1/auth/google/callback?code=c&state=s")
    assert resp.status_code == 400


def test_oauth_callback_happy_path_sets_cookie_and_redirects(client, monkeypatch):
    stored = {"provider": "google", "code_verifier": "v", "return_to": "/"}
    monkeypatch.setattr(auth_module.state_store, "pop_state", AsyncMock(return_value=stored))
    monkeypatch.setattr(
        auth_module,
        "exchange_code_for_tokens",
        AsyncMock(return_value=SimpleNamespace(access_token="a", refresh_token="r", expires_at=datetime.now(timezone.utc))),
    )
    monkeypatch.setattr(
        auth_module,
        "fetch_profile",
        AsyncMock(return_value=SimpleNamespace(provider_user_id="p1", name="N", email="e", avatar_url=None)),
    )
    monkeypatch.setattr(auth_module, "_upsert_user", AsyncMock(return_value=SimpleNamespace(id="u1")))
    monkeypatch.setattr(auth_module.session_store, "create_session", AsyncMock())
    monkeypatch.setattr(auth_module, "generate_session_id", lambda: "sid")

    resp = client.get("/api/v1/auth/google/callback?code=c&state=s", follow_redirects=False)
    assert resp.status_code == 302
    assert auth_module.settings.session_cookie_name in resp.headers.get("set-cookie", "")


def test_logout_clears_cookie(client, monkeypatch):
    monkeypatch.setattr(auth_module.session_store, "delete_session", AsyncMock())
    resp = client.post("/api/v1/auth/logout", cookies={auth_module.settings.session_cookie_name: "sid"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
