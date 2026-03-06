from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.frontend_routing import FrontendRoutingService


@pytest.mark.anyio
async def test_frontend_routing_service_helpers_and_cache():
    assert FrontendRoutingService._normalize_host("Example.COM:443") == "example.com"
    assert FrontendRoutingService._normalize_path("") == "/"
    assert FrontendRoutingService._normalize_path("a") == "/a"
    assert len(FrontendRoutingService._query_hash({"a": "1"})) == 12
    assert FrontendRoutingService._deep_merge({"a": {"b": 1}}, {"a": {"c": 2}}) == {"a": {"b": 1, "c": 2}}

    redis = AsyncMock()
    svc = FrontendRoutingService(db=AsyncMock(), redis=redis)

    redis.get = AsyncMock(return_value=None)
    assert await svc._cache_get("k") is None

    redis.get = AsyncMock(return_value="{bad-json")
    assert await svc._cache_get("k") is None


@pytest.mark.anyio
async def test_invalidate_runtime_cache_scans_and_deletes():
    redis = AsyncMock()
    redis.scan = AsyncMock(side_effect=[(1, ["a", "b"]), (0, ["c"])])
    redis.delete = AsyncMock()
    svc = FrontendRoutingService(db=AsyncMock(), redis=redis)

    await svc.invalidate_runtime_cache()
    assert redis.scan.await_count == 2
    assert redis.delete.await_count == 2


class _FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code


class _FakeAsyncClient:
    def __init__(self, *, timeout: float, follow_redirects: bool):
        self._head = AsyncMock(return_value=_FakeResponse(200))
        self._get = AsyncMock(return_value=_FakeResponse(200))

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def head(self, url: str):
        return await self._head(url)

    async def get(self, url: str):
        return await self._get(url)


@pytest.mark.anyio
async def test_validate_release_errors_and_success(monkeypatch):
    repo = SimpleNamespace(
        get_release=AsyncMock(return_value=None),
        update_release=AsyncMock(return_value=SimpleNamespace(health_status="unhealthy", validated_at=None)),
        has_allowed_host=AsyncMock(return_value=True),
    )
    svc = FrontendRoutingService(db=AsyncMock(), redis=None)
    svc.repo = repo

    with pytest.raises(ValueError):
        await svc.validate_release(1)

    repo.get_release = AsyncMock(
        return_value=SimpleNamespace(id=1, target_url="http://example.com", health_status="unknown", validated_at=None)
    )
    out = await svc.validate_release(1)
    assert out["ok"] is False
    assert out["reason"].startswith("target_url must use https")

    repo.get_release = AsyncMock(return_value=SimpleNamespace(id=1, target_url="https://", health_status="unknown", validated_at=None))
    out2 = await svc.validate_release(1)
    assert out2["ok"] is False
    assert "host is empty" in out2["reason"]

    repo.get_release = AsyncMock(
        return_value=SimpleNamespace(id=1, target_url="https://not-allowed.example/x", health_status="unknown", validated_at=None)
    )
    repo.has_allowed_host = AsyncMock(return_value=False)
    out3 = await svc.validate_release(1)
    assert out3["ok"] is False
    assert "not in allowlist" in out3["reason"]

    # success path
    repo.has_allowed_host = AsyncMock(return_value=True)
    repo.get_release = AsyncMock(
        return_value=SimpleNamespace(id=1, target_url="https://example.com/x", health_status="unknown", validated_at=None)
    )
    repo.update_release = AsyncMock(return_value=SimpleNamespace(health_status="healthy", validated_at=None))
    monkeypatch.setattr("app.services.frontend_routing.httpx.AsyncClient", _FakeAsyncClient)

    out4 = await svc.validate_release(1)
    assert out4["ok"] is True
    assert out4["health_status"] == "healthy"


@pytest.mark.anyio
async def test_validate_release_network_error_sets_reason(monkeypatch):
    class _FailClient(_FakeAsyncClient):
        async def head(self, url: str):
            raise RuntimeError("nope")

    repo = SimpleNamespace(
        get_release=AsyncMock(
            return_value=SimpleNamespace(id=1, target_url="https://example.com/x", health_status="unknown", validated_at=None)
        ),
        update_release=AsyncMock(return_value=SimpleNamespace(health_status="unhealthy", validated_at=None)),
        has_allowed_host=AsyncMock(return_value=True),
    )
    svc = FrontendRoutingService(db=AsyncMock(), redis=None)
    svc.repo = repo
    monkeypatch.setattr("app.services.frontend_routing.httpx.AsyncClient", _FailClient)

    out = await svc.validate_release(1)
    assert out["ok"] is False
    assert out["reason"]

