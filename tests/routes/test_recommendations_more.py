from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from recommendations.models import QuizAnswers, RecommendationSession, RecipientProfile, RecipientResponse
from routes import recommendations as rec_module


def _session() -> RecommendationSession:
    full = RecipientProfile(
        id="r1",
        quiz_data=QuizAnswers(recipient_age=25, relationship="friend", vibe="cozy"),
    )
    return RecommendationSession(
        session_id="s1",
        recipient=RecipientResponse(id="r1", name="Test"),
        full_recipient=full,
        topics=[],
        tracks=[],
    )


@pytest.fixture
def app_and_manager():
    app = FastAPI()
    app.include_router(rec_module.router)

    manager = AsyncMock()
    manager.init_session = AsyncMock(return_value=_session())
    manager.interact = AsyncMock(return_value=_session())
    manager.recipient_service = SimpleNamespace(
        get_hypothesis=AsyncMock(return_value=None),
        update_hypothesis_reaction=AsyncMock(return_value=None),
    )
    manager.recommendation_service = SimpleNamespace(
        get_deep_dive_products=AsyncMock(return_value=[{"id": "p1"}]),
    )

    async def override_get_dialogue_manager():
        return manager

    app.dependency_overrides[rec_module.get_dialogue_manager] = override_get_dialogue_manager
    return app, manager


@pytest.fixture
def client(app_and_manager):
    app, _ = app_and_manager
    return TestClient(app)


def test_init_internal_error(client, app_and_manager):
    _, manager = app_and_manager
    manager.init_session = AsyncMock(side_effect=RuntimeError("boom"))
    payload = {"recipient_age": 25, "relationship": "friend", "vibe": "cozy"}
    resp = client.post("/api/v1/recommendations/init", json=payload)
    assert resp.status_code == 500


def test_interact_value_error_maps_to_404(client, app_and_manager):
    _, manager = app_and_manager
    manager.interact = AsyncMock(side_effect=ValueError("missing"))
    payload = {"session_id": "s1", "action": "x", "value": None, "metadata": {}}
    resp = client.post("/api/v1/recommendations/interact", json=payload)
    assert resp.status_code == 404


def test_interact_internal_error(client, app_and_manager):
    _, manager = app_and_manager
    manager.interact = AsyncMock(side_effect=RuntimeError("boom"))
    payload = {"session_id": "s1", "action": "x", "value": None, "metadata": {}}
    resp = client.post("/api/v1/recommendations/interact", json=payload)
    assert resp.status_code == 500


def test_get_hypothesis_products_invalid_uuid(client):
    resp = client.get("/api/v1/recommendations/hypothesis/not-a-uuid/products")
    assert resp.status_code == 400


def test_get_hypothesis_products_not_found(client):
    resp = client.get("/api/v1/recommendations/hypothesis/00000000-0000-0000-0000-000000000001/products")
    assert resp.status_code == 404


def test_get_hypothesis_products_success(client, app_and_manager):
    _, manager = app_and_manager
    manager.recipient_service.get_hypothesis = AsyncMock(
        return_value=SimpleNamespace(
            id="h1",
            title="T",
            description="D",
            search_queries=["q1"],
        )
    )
    resp = client.get("/api/v1/recommendations/hypothesis/00000000-0000-0000-0000-000000000001/products")
    assert resp.status_code == 200
    assert resp.json() == [{"id": "p1"}]


def test_react_to_hypothesis_invalid_uuid(client):
    resp = client.post("/api/v1/recommendations/hypothesis/not-a-uuid/react?reaction=like")
    assert resp.status_code == 400


def test_react_to_hypothesis_not_found(client):
    resp = client.post("/api/v1/recommendations/hypothesis/00000000-0000-0000-0000-000000000001/react?reaction=like")
    assert resp.status_code == 404


def test_react_to_hypothesis_success(client, app_and_manager):
    _, manager = app_and_manager
    manager.recipient_service.update_hypothesis_reaction = AsyncMock(
        return_value=SimpleNamespace(id="00000000-0000-0000-0000-000000000001", user_reaction="like")
    )
    resp = client.post("/api/v1/recommendations/hypothesis/00000000-0000-0000-0000-000000000001/react?reaction=like")
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"


def test_get_hypothesis_products_unhandled_error_returns_500(client, app_and_manager):
    _, manager = app_and_manager
    manager.recipient_service.get_hypothesis = AsyncMock(
        return_value=SimpleNamespace(
            id="h1",
            title="T",
            description="D",
            search_queries=["q1"],
        )
    )
    manager.recommendation_service.get_deep_dive_products = AsyncMock(side_effect=RuntimeError("boom"))
    resp = client.get("/api/v1/recommendations/hypothesis/00000000-0000-0000-0000-000000000001/products")
    assert resp.status_code == 500


def test_react_to_hypothesis_unhandled_error_returns_500(client, app_and_manager):
    _, manager = app_and_manager
    manager.recipient_service.update_hypothesis_reaction = AsyncMock(side_effect=RuntimeError("boom"))
    resp = client.post("/api/v1/recommendations/hypothesis/00000000-0000-0000-0000-000000000001/react?reaction=like")
    assert resp.status_code == 500
