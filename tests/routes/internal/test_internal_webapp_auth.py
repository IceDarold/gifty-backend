from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from routes import internal as internal_routes


def _init_data_for_user(user_id: int) -> str:
    # Minimal querystring that routes/internal.py parses via parse_qsl + json.loads.
    return f'user=%7B%22id%22%3A{user_id}%7D'


def test_webapp_auth_dev_parses_init_data_and_allows_admin(client, monkeypatch):
    monkeypatch.setattr(internal_routes.settings, "env", "dev", raising=False)
    monkeypatch.setattr(internal_routes.settings, "telegram_bot_token", "t", raising=False)
    monkeypatch.setattr(internal_routes, "verify_telegram_init_data", lambda *_: True, raising=True)

    repo = SimpleNamespace(
        get_subscriber=AsyncMock(
            return_value=SimpleNamespace(chat_id=111, name="N", role="admin", permissions=["x"])
        )
    )
    monkeypatch.setattr(internal_routes, "TelegramRepository", lambda db: repo, raising=True)

    resp = client.post("/api/v1/internal/webapp/auth", json={"init_data": _init_data_for_user(111)})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "ok"
    assert body["user"]["id"] == 111


def test_webapp_auth_denies_when_subscriber_missing(client, monkeypatch):
    monkeypatch.setattr(internal_routes.settings, "env", "dev", raising=False)
    monkeypatch.setattr(internal_routes.settings, "telegram_bot_token", "t", raising=False)
    monkeypatch.setattr(internal_routes, "verify_telegram_init_data", lambda *_: True, raising=True)

    repo = SimpleNamespace(get_subscriber=AsyncMock(return_value=None))
    monkeypatch.setattr(internal_routes, "TelegramRepository", lambda db: repo, raising=True)

    resp = client.post("/api/v1/internal/webapp/auth", json={"init_data": _init_data_for_user(222)})
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_verify_internal_token_parses_tg_init_data(monkeypatch, fake_db):
    monkeypatch.setattr(internal_routes.settings, "env", "prod", raising=False)
    monkeypatch.setattr(internal_routes.settings, "telegram_bot_token", "t", raising=False)
    monkeypatch.setattr(internal_routes, "verify_telegram_init_data", lambda *_: True, raising=True)

    repo = SimpleNamespace(get_subscriber=AsyncMock(return_value=SimpleNamespace(chat_id=123, role="superadmin")))
    monkeypatch.setattr(internal_routes, "TelegramRepository", lambda db: repo, raising=True)

    token = await internal_routes.verify_internal_token(x_internal_token=None, x_tg_init_data=_init_data_for_user(123), db=fake_db)
    assert token == "tg_admin:123"

