from __future__ import annotations

from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from routes import internal as internal_routes


@pytest.mark.asyncio
async def test_verify_internal_token_accepts_system_token(monkeypatch):
    monkeypatch.setattr(internal_routes.settings, "internal_api_token", "secret")
    db = AsyncMock()
    principal = await internal_routes.verify_internal_token(x_internal_token="secret", x_tg_init_data=None, db=db)
    assert principal == "secret"


@pytest.mark.asyncio
async def test_verify_internal_token_rejects_wrong_system_token(monkeypatch):
    monkeypatch.setattr(internal_routes.settings, "internal_api_token", "secret")
    db = AsyncMock()
    with pytest.raises(Exception) as exc:
        await internal_routes.verify_internal_token(x_internal_token="nope", x_tg_init_data=None, db=db)
    assert getattr(exc.value, "status_code", None) == 403


@pytest.mark.asyncio
async def test_verify_internal_token_tg_init_data_invalid_signature(monkeypatch):
    monkeypatch.setattr(internal_routes.settings, "telegram_bot_token", "bot-token")
    monkeypatch.setattr(internal_routes, "verify_telegram_init_data", lambda *args, **kwargs: False)
    db = AsyncMock()
    with pytest.raises(Exception) as exc:
        await internal_routes.verify_internal_token(x_internal_token=None, x_tg_init_data="user=%7B%22id%22%3A1%7D", db=db)
    assert getattr(exc.value, "status_code", None) == 403


@pytest.mark.asyncio
async def test_verify_internal_token_dev_bypass_sets_cache(monkeypatch):
    internal_routes._tg_admin_auth_cache.clear()
    monkeypatch.setattr(internal_routes.settings, "env", "dev")

    async def _get_subscriber(_self, _chat_id: int):
        return SimpleNamespace(role="admin")

    monkeypatch.setattr(internal_routes.TelegramRepository, "get_subscriber", _get_subscriber, raising=True)
    db = AsyncMock()

    principal = await internal_routes.verify_internal_token(
        x_internal_token=None,
        x_tg_init_data="dev_user_1821014162",
        db=db,
    )
    assert principal == "tg_admin:1821014162"
    cached_until = internal_routes._tg_admin_auth_cache.get(1821014162)
    assert isinstance(cached_until, datetime)
    assert cached_until > datetime.now(timezone.utc) - timedelta(seconds=1)


@pytest.mark.asyncio
async def test_verify_internal_token_uses_cache(monkeypatch):
    internal_routes._tg_admin_auth_cache.clear()
    monkeypatch.setattr(internal_routes.settings, "env", "dev")

    get_subscriber = AsyncMock(return_value=SimpleNamespace(role="superadmin"))
    monkeypatch.setattr(internal_routes.TelegramRepository, "get_subscriber", get_subscriber, raising=True)
    db = AsyncMock()

    principal1 = await internal_routes.verify_internal_token(x_internal_token=None, x_tg_init_data="dev_user_1821014162", db=db)
    principal2 = await internal_routes.verify_internal_token(x_internal_token=None, x_tg_init_data="dev_user_1821014162", db=db)

    assert principal1 == "tg_admin:1821014162"
    assert principal2 == "tg_admin:1821014162"
    assert get_subscriber.await_count == 1

