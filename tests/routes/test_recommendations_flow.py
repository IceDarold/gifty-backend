from __future__ import annotations

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
def client():
    app = FastAPI()
    app.include_router(rec_module.router)

    manager = AsyncMock()
    manager.init_session = AsyncMock(return_value=_session())
    manager.interact = AsyncMock(return_value=_session())

    async def override_get_dialogue_manager():
        return manager

    app.dependency_overrides[rec_module.get_dialogue_manager] = override_get_dialogue_manager
    return TestClient(app)


def test_init_ok(client):
    payload = {
        "recipient_age": 25,
        "relationship": "friend",
        "vibe": "cozy",
    }
    resp = client.post("/api/v1/recommendations/init", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"] == "s1"
    assert body["recipient"]["id"] == "r1"


def test_init_user_id_invalid_uuid(client):
    payload = {
        "recipient_age": 25,
        "relationship": "friend",
        "vibe": "cozy",
    }
    resp = client.post("/api/v1/recommendations/init?user_id=not-a-uuid", json=payload)
    assert resp.status_code == 400


def test_interact_ok(client):
    payload = {
        "session_id": "s1",
        "action": "like",
        "value": "hypothesis-1",
        "metadata": {"source": "test"},
    }
    resp = client.post("/api/v1/recommendations/interact", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"] == "s1"

