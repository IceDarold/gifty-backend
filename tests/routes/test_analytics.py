
import pytest
import httpx
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch
from app.main import app
from app.config import get_settings
from datetime import datetime

@pytest.fixture
def test_settings():
    settings = get_settings()
    settings.analytics_api_token = "test-token"
    settings.posthog_api_key = "ph-key"
    settings.posthog_project_id = "ph-id"
    settings.prometheus_url = "http://prom"
    settings.loki_url = "http://loki"
    return settings

@pytest.fixture(autouse=True)
def mock_dependencies():
    """Mock shared dependencies for all analytics tests."""
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    
    from app.redis_client import get_redis
    app.dependency_overrides[get_redis] = lambda: mock_redis
    
    # Initialize state.redis to avoid AttributeError in some paths
    app.state.redis = mock_redis
    
    yield
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_get_analytics_stats_unauthorized():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/analytics/stats")
        assert response.status_code == 422 # Missing header

@pytest.mark.asyncio
async def test_get_analytics_stats_invalid_token(test_settings):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(
            "/api/v1/analytics/stats", 
            headers={"X-Analytics-Token": "wrong"}
        )
        assert response.status_code == 403

@pytest.mark.asyncio
async def test_get_analytics_stats_success(test_settings):
    # Mock query_posthog instead of httpx calls for simplicity in this endpoint test
    with patch("routes.analytics.query_posthog") as mock_ph:
        mock_ph.side_effect = [
            {"results": [{"data": [100]}]}, # DAU
            {"results": [{"count": 200}, {"count": 100}]}, # Funnel Quiz
            {"results": [{"count": 1000}, {"count": 50}]} # Funnel Gift
        ]
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get(
                "/api/v1/analytics/stats",
                headers={"X-Analytics-Token": test_settings.analytics_api_token}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["dau"] == 100
            assert data["quiz_completion_rate"] == 50.0
            assert data["gift_ctr"] == 5.0
            assert data["total_sessions"] == 200

@pytest.mark.asyncio
async def test_get_technical_stats_success(test_settings):
    # Properly mock httpx.AsyncClient as a context manager
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        # 1. Prometheus RPM
        # 2. Prometheus Errors
        # 3. Loki Logs
        mock_client.get.side_effect = [
            MagicMock(status_code=200, json=lambda: {"data": {"result": [{"value": [0, "10.5"]}]}}),
            MagicMock(status_code=200, json=lambda: {"data": {"result": [{"value": [0, "0.01"]}]}}),
            MagicMock(status_code=200, json=lambda: {"data": {"result": [{"values": [[0, "error log line"]]}]}})
        ]
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get(
                "/api/v1/analytics/technical",
                headers={"X-Analytics-Token": test_settings.analytics_api_token}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["requests_per_minute"] == 10.5
            assert data["error_rate_5xx"] == 0.01
            assert "error log line" in data["last_errors"][0]

@pytest.mark.asyncio
async def test_get_scraping_monitoring(test_settings):
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = 5
    mock_db.execute.return_value = mock_result
    
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        mock_client.get.return_value = MagicMock(status_code=200, json=lambda: {"data": {"result": [{"value": [0, "100"], "metric": {"spider": "test"}}]}})
        
        from app.db import get_db
        app.dependency_overrides[get_db] = lambda: mock_db
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get(
                "/api/v1/analytics/scraping",
                headers={"X-Analytics-Token": test_settings.analytics_api_token}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["active_sources"] == 5
            assert data["total_scraped_items"] == 100
            
        app.dependency_overrides.clear()


