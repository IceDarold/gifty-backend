from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import recipients as recp_module


@pytest.fixture
def app_and_service(monkeypatch):
    app = FastAPI()
    app.include_router(recp_module.router)

    service = SimpleNamespace(
        get_user_recipients=AsyncMock(return_value=[]),
        get_recipient=AsyncMock(return_value=None),
        update_recipient=AsyncMock(return_value=None),
        get_recipient_interactions=AsyncMock(return_value=[]),
    )

    monkeypatch.setattr(recp_module, "RecipientService", lambda db: service)

    async def override_get_db():
        yield AsyncMock()

    app.dependency_overrides[recp_module.get_db] = override_get_db
    return app, service


@pytest.fixture
def client(app_and_service):
    app, _ = app_and_service
    return TestClient(app)


def test_list_recipients_ok(client, app_and_service):
    app, service = app_and_service
    rid = UUID("00000000-0000-0000-0000-000000000001")
    service.get_user_recipients = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=rid,
                user_id=rid,
                name="N",
                relation="friend",
                interests=["x"],
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        ]
    )
    resp = client.get(f"/api/v1/recipients/?user_id={rid}")
    assert resp.status_code == 200
    assert resp.json()[0]["id"] == str(rid)


def test_get_recipient_404(client):
    resp = client.get("/api/v1/recipients/00000000-0000-0000-0000-000000000001")
    assert resp.status_code == 404


def test_get_recipient_ok(client, app_and_service):
    _, service = app_and_service
    rid = UUID("00000000-0000-0000-0000-000000000001")
    service.get_recipient = AsyncMock(
        return_value=SimpleNamespace(
            id=rid,
            user_id=None,
            name="N",
            relation=None,
            interests=[],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )
    resp = client.get(f"/api/v1/recipients/{rid}")
    assert resp.status_code == 200
    assert resp.json()["id"] == str(rid)


def test_update_recipient_404(client):
    resp = client.put(
        "/api/v1/recipients/00000000-0000-0000-0000-000000000001",
        json={"name": "X", "interests": ["a"]},
    )
    assert resp.status_code == 404


def test_update_recipient_ok(client, app_and_service):
    _, service = app_and_service
    rid = UUID("00000000-0000-0000-0000-000000000001")
    service.update_recipient = AsyncMock(
        return_value=SimpleNamespace(
            id=rid,
            user_id=None,
            name="X",
            relation=None,
            interests=["a"],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )
    resp = client.put(f"/api/v1/recipients/{rid}", json={"name": "X", "interests": ["a"]})
    assert resp.status_code == 200
    assert resp.json()["name"] == "X"


def test_recipient_history_404(client):
    resp = client.get("/api/v1/recipients/00000000-0000-0000-0000-000000000001/history")
    assert resp.status_code == 404


def test_recipient_history_ok(client, app_and_service):
    _, service = app_and_service
    rid = UUID("00000000-0000-0000-0000-000000000001")
    service.get_recipient = AsyncMock(return_value=SimpleNamespace(id=rid))
    service.get_recipient_interactions = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=UUID("00000000-0000-0000-0000-000000000002"),
                recipient_id=rid,
                session_id="s",
                action_type="like",
                target_type="hypothesis",
                target_id="h",
                value=None,
                metadata_json={},
                created_at=datetime.now(timezone.utc),
            )
        ]
    )
    resp = client.get(f"/api/v1/recipients/{rid}/history?limit=1")
    assert resp.status_code == 200
    assert resp.json()[0]["session_id"] == "s"

