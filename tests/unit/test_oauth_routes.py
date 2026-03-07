from __future__ import annotations

import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.auth import routes as auth_routes
from app.utils.errors import AppError


class FakePipeline:
    def __init__(self, redis: "FakeRedis"):
        self._redis = redis
        self._ops = []

    def get(self, key: str):
        self._ops.append(("get", key))
        return self

    def delete(self, key: str):
        self._ops.append(("del", key))
        return self

    async def execute(self):
        out = []
        for op, key in self._ops:
            if op == "get":
                out.append(await self._redis.get(key))
            else:
                out.append(await self._redis.delete(key))
        return out


class FakeRedis:
    def __init__(self):
        self._kv = {}

    async def set(self, key, value, ex=None):
        self._kv[key] = value
        return True

    async def get(self, key):
        return self._kv.get(key)

    async def delete(self, key):
        self._kv.pop(key, None)
        return 1

    def pipeline(self):
        return FakePipeline(self)


def test_safe_return_to():
    assert auth_routes._safe_return_to(None) == "/"
    assert auth_routes._safe_return_to("//evil.com") == "/"
    assert auth_routes._safe_return_to("not-a-path") == "/"


@pytest.mark.asyncio
async def test_oauth_start_saves_state_and_redirect(monkeypatch):
    redis = FakeRedis()
    cfg = SimpleNamespace(
        name="google",
        authorize_url="https://auth.example/authorize",
        token_url="https://auth.example/token",
        userinfo_url="https://auth.example/userinfo",
        scopes=["openid"],
        client_id="cid",
        client_secret="csecret",
        extra_auth_params=None,
    )
    monkeypatch.setattr(auth_routes, "get_provider_config", lambda provider, settings: cfg)
    monkeypatch.setattr(auth_routes, "build_authorize_url", lambda *args, **kwargs: "https://auth.example/authorize?x=1")

    resp = await auth_routes.oauth_start(provider="google", redis=redis, return_to="/x")
    assert resp.status_code == 302
    assert resp.headers["location"].startswith("https://auth.example/authorize")
    assert any(k.startswith("oauth_state:") for k in redis._kv.keys())


@pytest.mark.asyncio
async def test_oauth_callback_missing_params():
    with pytest.raises(AppError) as exc:
        await auth_routes.oauth_callback(provider="google", code=None, state=None, redis=FakeRedis(), db=AsyncMock())
    assert exc.value.http_status == 400


@pytest.mark.asyncio
async def test_oauth_callback_invalid_state(monkeypatch):
    monkeypatch.setattr(auth_routes.state_store, "pop_state", AsyncMock(return_value=None))
    with pytest.raises(AppError) as exc:
        await auth_routes.oauth_callback(provider="google", code="1", state="2", redis=FakeRedis(), db=AsyncMock())
    assert exc.value.http_status == 400

