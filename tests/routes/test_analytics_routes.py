from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import analytics as analytics_routes


class _FakeSettings:
    analytics_api_token = "token"
    prometheus_url = "http://prom"
    loki_url = "http://loki"


class _FakeRedis:
    def __init__(self):
        self._kv = {}

    async def get(self, key: str):
        return self._kv.get(key)

    async def setex(self, key: str, ttl: int, value: str):
        self._kv[key] = value
        return True


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(analytics_routes.router)

    async def override_settings():
        return _FakeSettings()

    async def override_db():
        yield AsyncMock(execute=AsyncMock(return_value=_ScalarResult(0)))

    fake_redis = _FakeRedis()

    async def override_redis():
        return fake_redis

    app.dependency_overrides[analytics_routes.get_settings] = lambda: _FakeSettings()
    app.dependency_overrides[analytics_routes.get_db] = override_db
    app.dependency_overrides[analytics_routes.get_redis] = override_redis
    return TestClient(app), fake_redis


def test_verify_token_via_analytics_token(client, monkeypatch):
    c, _ = client
    resp = c.get("/api/v1/analytics/technical", headers={"X-Analytics-Token": "token"})
    assert resp.status_code == 200


def test_verify_token_via_internal_auth_fallback(client, monkeypatch):
    c, _ = client
    import routes.internal as internal_routes

    called = AsyncMock(return_value="internal")
    monkeypatch.setattr(internal_routes, "verify_internal_token", called, raising=True)
    resp = c.get("/api/v1/analytics/technical", headers={"X-Internal-Token": "t"})
    assert resp.status_code == 200
    assert called.await_count == 1


def test_technical_and_scraping_cached_and_fetch(client, monkeypatch):
    c, redis = client

    # Cached technical
    redis._kv["analytics:technical_stats"] = json.dumps({"api_health": "healthy"})
    resp = c.get("/api/v1/analytics/technical", headers={"X-Analytics-Token": "token"})
    assert resp.status_code == 200
    assert resp.json()["api_health"] == "healthy"

    # Fetch path for technical + scraping use httpx
    redis._kv.clear()

    class _Resp:
        def __init__(self, payload):
            self.status_code = 200
            self._payload = payload

        def json(self):
            return self._payload

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, params=None):
            q = (params or {}).get("query")
            if q and "http_request_duration_seconds_count" in q:
                return _Resp({"data": {"result": [{"value": [0, "1"]}]}})
            if q and "sum by (spider)" in q:
                return _Resp({"data": {"result": [{"metric": {"spider": "s"}, "value": [0, "3"]}]}})
            if q and "scraped_items_total" in q:
                return _Resp({"data": {"result": [{"value": [0, "10"]}]}})
            if q and "ingestion_batches_total" in q:
                return _Resp({"data": {"result": [{"value": [0, "2"]}]}})
            # Loki errors
            return _Resp({"data": {"result": [{"values": [["1", "err"]]}]}})

    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", lambda timeout=5.0: _Client())

    tech = c.get("/api/v1/analytics/technical", headers={"X-Analytics-Token": "token"})
    assert tech.status_code == 200

    scrape = c.get("/api/v1/analytics/scraping", headers={"X-Analytics-Token": "token"})
    assert scrape.status_code == 200
    assert scrape.json()["spiders"]["s"]["items_scraped"] == 3


def test_trends_and_funnel_endpoints(monkeypatch):
    app = FastAPI()
    app.include_router(analytics_routes.router)

    app.dependency_overrides[analytics_routes.get_settings] = lambda: _FakeSettings()
    redis = _FakeRedis()

    async def override_redis():
        return redis

    async def override_db():
        yield AsyncMock(execute=AsyncMock(return_value=_ScalarResult(0)))

    app.dependency_overrides[analytics_routes.get_redis] = override_redis
    app.dependency_overrides[analytics_routes.get_db] = override_db

    import app.analytics.schema as schema_mod

    async def _fake_posthog(query, settings, redis, cache_key, cache_ttl=300):
        if query.get("kind") == "TrendsQuery":
            return {"results": [{"labels": ["a"], "data": [1]}]}
        return {"results": [{"name": "Step 1", "count": 1, "conversionRates": {"total": 1.0}}]}

    monkeypatch.setattr(schema_mod, "query_posthog", _fake_posthog, raising=True)

    client = TestClient(app)
    resp = client.get("/api/v1/analytics/trends", headers={"X-Analytics-Token": "token"})
    assert resp.status_code == 200
    resp2 = client.get("/api/v1/analytics/funnel", headers={"X-Analytics-Token": "token"})
    assert resp2.status_code == 200
    assert resp2.json()["steps"][0]["count"] == 1
