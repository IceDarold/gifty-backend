from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture()
def mock_redis():
    redis = AsyncMock()
    redis.incr.return_value = 1
    redis.expire.return_value = True
    return redis


@pytest.fixture(autouse=True)
def _override_deps(mock_redis):
    from app.redis_client import get_redis as get_redis_from_state
    from app.db import get_redis as get_redis_from_db
    from routes.internal import verify_internal_token

    async def _redis_override():
        return mock_redis

    async def _auth_override():
        return "ok"

    app.dependency_overrides[get_redis_from_state] = _redis_override
    app.dependency_overrides[get_redis_from_db] = _redis_override
    app.dependency_overrides[verify_internal_token] = _auth_override
    app.state.redis = mock_redis
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_internal_posthog_stats_success(monkeypatch, mock_redis):
    from routes import internal_posthog

    async def _fake_kpis(*_args, **_kwargs):
        return {
            "dau": 12,
            "quiz_completion_rate": 33.3,
            "gift_ctr": 22.2,
            "total_sessions": 100,
            "source": "live",
            "stale": False,
            "cache_age_seconds": 0,
            "last_updated": "2026-03-07T00:00:00+00:00",
        }

    monkeypatch.setattr(internal_posthog, "get_posthog_kpis", _fake_kpis)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/internal/analytics/posthog/stats", headers={"X-Internal-Token": "x"})

    assert res.status_code == 200
    body = res.json()
    assert body["dau"] == 12
    assert body["source"] == "live"
    assert body["stale"] is False


@pytest.mark.asyncio
async def test_internal_posthog_stats_rate_limit(mock_redis):
    mock_redis.incr.return_value = 999

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/internal/analytics/posthog/stats", headers={"X-Internal-Token": "x"})

    assert res.status_code == 429


@pytest.mark.asyncio
async def test_internal_posthog_stats_allowlist(monkeypatch, mock_redis):
    from routes import internal_posthog

    settings = internal_posthog.get_settings()
    original = settings.posthog_stats_allowlist_ips
    settings.posthog_stats_allowlist_ips = "10.10.10.10"

    async def _fake_kpis(*_args, **_kwargs):
        return {
            "dau": 1,
            "quiz_completion_rate": 1.0,
            "gift_ctr": 1.0,
            "total_sessions": 1,
            "source": "live",
            "stale": False,
            "cache_age_seconds": 0,
            "last_updated": "2026-03-07T00:00:00+00:00",
        }

    monkeypatch.setattr(internal_posthog, "get_posthog_kpis", _fake_kpis)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            res = await ac.get("/api/v1/internal/analytics/posthog/stats", headers={"X-Internal-Token": "x"})
        assert res.status_code == 403
    finally:
        settings.posthog_stats_allowlist_ips = original
