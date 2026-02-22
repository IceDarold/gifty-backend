from __future__ import annotations
import uuid
from types import SimpleNamespace
from typing import Any
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock

from routes import recommendations as rec_module
from app.schemas_v2 import RecommendationResponse, GiftDTO

@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(rec_module.router)
    
    # Mocking app.state
    app.state.embedding_service = MagicMock()
    
    async def override_get_db():
        yield AsyncMock()

    async def override_get_redis():
        return AsyncMock()

    app.dependency_overrides[rec_module.get_db] = override_get_db
    app.dependency_overrides[rec_module.get_redis] = override_get_redis
    app.dependency_overrides[rec_module.get_optional_user] = lambda: None

    return TestClient(app)

@pytest.fixture
def service_mock(monkeypatch):
    mock_service = AsyncMock()
    
    sample_gifts = [
        GiftDTO(
            id=f"gift-{i}",
            title=f"Gift {i}",
            description="Description",
            price=10.0 + i,
            currency="RUB",
            product_url=f"http://example.com/{i}",
        ) for i in range(5)
    ]
    
    mock_service.generate_recommendations.return_value = RecommendationResponse(
        quiz_run_id="test-run-id",
        engine_version="test-v1",
        featured_gift=sample_gifts[0],
        gifts=sample_gifts,
        debug={"test": True}
    )
    
    # Mock the class instantiation
    monkeypatch.setattr("routes.recommendations.RecommendationService", lambda db, emb: mock_service)
    # Also mock repositories used in the route
    monkeypatch.setattr("routes.recommendations.create_quiz_run", AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4())))
    monkeypatch.setattr("routes.recommendations.log_event", AsyncMock())
    
    return mock_service

def _payload(debug: bool = False) -> dict[str, Any]:
    return {
        "recipient_age": 25,
        "relationship": "friend",
        "vibe": "cozy",
        "top_n": 5,
        "debug": debug,
    }

def test_generate_happy_path(client, service_mock):
    response = client.post("/api/v1/recommendations/generate", json=_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["featured_gift"]["id"] == "gift-0"
    assert len(body["gifts"]) == 5
    assert body["quiz_run_id"] is not None

def test_generate_debug_mode(client, service_mock):
    response = client.post("/api/v1/recommendations/generate", json=_payload(debug=True))
    assert response.status_code == 200
    body = response.json()
    assert body["debug"] == {"test": True}
