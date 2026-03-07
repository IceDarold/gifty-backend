from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.auth import providers
from app.utils.errors import AppError


def _settings():
    return SimpleNamespace(
        google_authorize_url="https://google/auth",
        google_token_url="https://google/token",
        google_userinfo_url="https://google/userinfo",
        google_client_id="gid",
        google_client_secret="gsecret",
        yandex_authorize_url="https://y/auth",
        yandex_token_url="https://y/token",
        yandex_userinfo_url="https://y/userinfo",
        yandex_client_id="yid",
        yandex_client_secret="ysecret",
        vk_authorize_url="https://vk/auth",
        vk_token_url="https://vk/token",
        vk_userinfo_url="https://vk/userinfo",
        vk_client_id="vkid",
        vk_client_secret="vksecret",
        vk_api_version="5.199",
    )


def test_get_provider_config_variants():
    s = _settings()
    assert providers.get_provider_config("google", s).name == "google"
    assert providers.get_provider_config("YANDEX", s).name == "yandex"
    assert providers.get_provider_config("vk", s).name == "vk"
    with pytest.raises(AppError):
        providers.get_provider_config("unknown", s)


def test_build_authorize_url_includes_extra_params():
    cfg = providers.ProviderConfig(
        name="google",
        authorize_url="https://x/auth",
        token_url="t",
        userinfo_url="u",
        scopes=["a", "b"],
        client_id="cid",
        client_secret="sec",
        extra_auth_params={"prompt": "consent"},
    )
    url = providers.build_authorize_url(cfg, redirect_uri="https://cb", state="s", code_challenge="c")
    assert url.startswith("https://x/auth?")
    assert "prompt=consent" in url


@pytest.mark.asyncio
async def test_exchange_code_for_tokens_happy(monkeypatch):
    cfg = providers.ProviderConfig(
        name="google",
        authorize_url="a",
        token_url="https://x/token",
        userinfo_url="u",
        scopes=["a"],
        client_id="cid",
        client_secret="sec",
    )

    class _Resp:
        status_code = 200

        def json(self):
            return {"access_token": "t", "refresh_token": "r", "expires_in": 10, "id_token": "id"}

        text = "ok"

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, data=None):
            return _Resp()

    monkeypatch.setattr(providers, "_http_client", lambda: _Client())
    out = await providers.exchange_code_for_tokens(cfg, code="c", redirect_uri="https://cb", code_verifier="v")
    assert out.access_token == "t"
    assert out.refresh_token == "r"
    assert out.expires_at is not None


@pytest.mark.asyncio
async def test_exchange_code_for_tokens_errors(monkeypatch):
    cfg = providers.ProviderConfig(
        name="google",
        authorize_url="a",
        token_url="https://x/token",
        userinfo_url="u",
        scopes=["a"],
        client_id="cid",
        client_secret="sec",
    )

    class _RespBad:
        status_code = 500
        text = "bad"

        def json(self):
            return {}

    class _RespNoToken:
        status_code = 200
        text = "ok"

        def json(self):
            return {}

    class _Client:
        def __init__(self, resp):
            self._resp = resp

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, data=None):
            return self._resp

    monkeypatch.setattr(providers, "_http_client", lambda: _Client(_RespBad()))
    with pytest.raises(AppError):
        await providers.exchange_code_for_tokens(cfg, code="c", redirect_uri="https://cb", code_verifier="v")

    monkeypatch.setattr(providers, "_http_client", lambda: _Client(_RespNoToken()))
    with pytest.raises(AppError):
        await providers.exchange_code_for_tokens(cfg, code="c", redirect_uri="https://cb", code_verifier="v")


@pytest.mark.asyncio
async def test_fetch_profile_variants(monkeypatch):
    s = _settings()

    class _Resp:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload
            self.text = "x"

        def json(self):
            return self._payload

    class _Client:
        def __init__(self, resp):
            self._resp = resp

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers=None, params=None):
            return self._resp

    tokens = providers.TokenResult(access_token="t", refresh_token=None, expires_at=None, id_token=None, raw={"email": "vk@mail"})

    gcfg = providers.get_provider_config("google", s)
    monkeypatch.setattr(providers, "_http_client", lambda: _Client(_Resp(200, {"sub": "1", "email": "e", "name": "n", "picture": "p"})))
    g = await providers.fetch_profile(gcfg, tokens, s)
    assert g.provider_user_id == "1"

    ycfg = providers.get_provider_config("yandex", s)
    monkeypatch.setattr(providers, "_http_client", lambda: _Client(_Resp(200, {"id": "2", "emails": ["a@b"], "real_name": "R", "default_avatar_id": "x"})))
    y = await providers.fetch_profile(ycfg, tokens, s)
    assert y.provider_user_id == "2"
    assert y.email == "a@b"

    vkcfg = providers.get_provider_config("vk", s)
    monkeypatch.setattr(providers, "_http_client", lambda: _Client(_Resp(200, {"response": [{"id": 3, "first_name": "A", "last_name": "B", "photo_200": "ph"}]})))
    v = await providers.fetch_profile(vkcfg, tokens, s)
    assert v.provider_user_id == "3"
    assert v.email == "vk@mail"

