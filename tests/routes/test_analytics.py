import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch
from app.main import app
from app.config import get_settings
from types import SimpleNamespace

@pytest.fixture
def test_settings():
    settings = get_settings()
    settings.analytics_api_token = "test-token"
    settings.internal_api_token = "internal-test-token"
    settings.env = "dev"
    return settings

@pytest.fixture(autouse=True)
def mock_dependencies():
    """Mock shared dependencies for all analytics tests."""
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    
    from app.redis_client import get_redis
    # FastAPI inspects dependency signatures; varargs/kwargs become required query params ("args"/"kwargs"),
    # which yields 422 in tests. Match the real signature instead.
    from fastapi import Request
    async def _get_redis_override(request: Request):
        return mock_redis
    app.dependency_overrides[get_redis] = _get_redis_override
    
    # Initialize state.redis to avoid AttributeError in some paths
    app.state.redis = mock_redis
    
    yield
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_analytics_graphql_unauthorized():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Request to GraphQL endpoint without token
        response = await ac.post(
            "/api/v1/analytics/graphql",
            json={"query": "{ stats { dau } }"}
        )
        assert response.status_code in (403, 422)

@pytest.mark.asyncio
async def test_analytics_graphql_invalid_token(test_settings):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/analytics/graphql",
            headers={"X-Analytics-Token": "wrong-token"},
            json={"query": "{ stats { dau } }"}
        )
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_analytics_rest_trends_ok(test_settings):
    with patch("app.analytics.schema.Query.trends", new=AsyncMock(return_value=SimpleNamespace(
        dates=["2026-03-01"],
        dau_trend=[1],
        quiz_starts=[2],
        last_updated="2026-03-04T00:00:00Z",
    ))):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get(
                "/api/v1/analytics/trends",
                headers={"X-Analytics-Token": test_settings.analytics_api_token},
            )
            assert response.status_code == 200
            payload = response.json()
            assert payload["dates"] == ["2026-03-01"]

            alias = await ac.get(
                "/api/v1/analytics/stats/trends",
                headers={"X-Analytics-Token": test_settings.analytics_api_token},
            )
            assert alias.status_code == 200


@pytest.mark.asyncio
async def test_analytics_rest_internal_auth_fallback(monkeypatch):
    # No analytics token, but internal token path works.
    monkeypatch.setattr("routes.internal.verify_internal_token", AsyncMock(return_value="ok"))
    with patch("app.analytics.schema.Query.trends", new=AsyncMock(return_value=SimpleNamespace(
        dates=[],
        dau_trend=[],
        quiz_starts=[],
        last_updated="now",
    ))):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get(
                "/api/v1/analytics/trends",
                headers={"X-Internal-Token": "any"},
            )
            assert response.status_code == 200


@pytest.mark.asyncio
async def test_analytics_rest_technical_cache_hit(test_settings):
    # When cached, endpoint returns cached payload and does not call httpx.
    cached = {"api_health": "healthy", "requests_per_minute": 1, "error_rate_5xx": 0, "active_workers": 0, "last_errors": [], "last_updated": "x"}
    app.state.redis.get.return_value = __import__("json").dumps(cached)
    with patch("httpx.AsyncClient") as mock_client:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get(
                "/api/v1/analytics/technical",
                headers={"X-Analytics-Token": test_settings.analytics_api_token},
            )
            assert response.status_code == 200
            assert response.json()["api_health"] == "healthy"
    mock_client.assert_not_called()


@pytest.mark.asyncio
async def test_analytics_rest_technical_cache_miss_sets_cache(test_settings):
    app.state.redis.get.return_value = None
    app.state.redis.setex = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        mock_client.get.side_effect = [
            MagicMock(status_code=200, json=lambda: {"data": {"result": [{"value": [0, "10.5"]}]}}),  # RPM
            MagicMock(status_code=200, json=lambda: {"data": {"result": [{"value": [0, "0.01"]}]}}),  # Errors
            MagicMock(status_code=200, json=lambda: {"data": {"result": [{"values": [[0, "error log line"]]}]}}),  # Loki
        ]

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get(
                "/api/v1/analytics/technical",
                headers={"X-Analytics-Token": test_settings.analytics_api_token},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["requests_per_minute"] == 10.5
            assert data["error_rate_5xx"] == 0.01
            assert "error log line" in data["last_errors"][0]

    assert app.state.redis.setex.await_count == 1

@pytest.mark.asyncio
async def test_get_stats_graphql_success(test_settings):
    # Mock query_posthog in app.analytics.schema
    with patch("app.analytics.schema.query_posthog") as mock_ph:
        mock_ph.side_effect = [
            {"results": [{"data": [100]}]}, # DAU
            {"results": [{"count": 200}, {"count": 100}]}, # Funnel Quiz
            {"results": [{"count": 1000}, {"count": 50}]} # Funnel Gift
        ]
        
        query = """
        query {
          stats {
            dau
            quizCompletionRate
            giftCtr
            totalSessions
          }
        }
        """
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/analytics/graphql",
                headers={"X-Analytics-Token": test_settings.analytics_api_token},
                json={"query": query}
            )
            
            assert response.status_code == 200
            data = response.json()["data"]["stats"]
            assert data["dau"] == 100
            assert data["quizCompletionRate"] == 50.0
            assert data["giftCtr"] == 5.0
            assert data["totalSessions"] == 200

@pytest.mark.asyncio
async def test_get_technical_graphql_success(test_settings):
    # Mock query_prometheus and query_loki in app.analytics.schema
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        mock_client.get.side_effect = [
            MagicMock(status_code=200, json=lambda: {"data": {"result": [{"value": [0, "10.5"]}]}}), # RPM
            MagicMock(status_code=200, json=lambda: {"data": {"result": [{"value": [0, "0.01"]}]}}), # Errors
            MagicMock(status_code=200, json=lambda: {"data": {"result": [{"values": [[0, "error log line"]]}]}}) # Loki
        ]
        
        query = """
        query {
          technical {
            requestsPerMinute
            errorRate5xx
            lastErrors
          }
        }
        """
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/analytics/graphql",
                headers={"X-Analytics-Token": test_settings.analytics_api_token},
                json={"query": query}
            )
            
            assert response.status_code == 200
            data = response.json()["data"]["technical"]
            assert data["requestsPerMinute"] == 10.5
            assert data["errorRate5xx"] == 0.01
            assert "error log line" in data["lastErrors"][0]

@pytest.mark.asyncio
async def test_get_scraping_monitoring_graphql_success(test_settings):
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = 5
    mock_db.execute.return_value = mock_result
    
    # Mock query_prometheus for scraped items
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client.get.return_value = MagicMock(status_code=200, json=lambda: {"data": {"result": [{"value": [0, "100"], "metric": {"spider": "test"}}]}})
        
        from app.db import get_db
        app.dependency_overrides[get_db] = lambda: mock_db
        
        query = """
        query {
          scraping {
            activeSources
            totalScrapedItems
          }
        }
        """
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/analytics/graphql",
                headers={"X-Analytics-Token": test_settings.analytics_api_token},
                json={"query": query}
            )
            
            assert response.status_code == 200
            data = response.json()["data"]["scraping"]
            assert data["activeSources"] == 5
            assert data["totalScrapedItems"] == 100
            
        app.dependency_overrides.clear()
