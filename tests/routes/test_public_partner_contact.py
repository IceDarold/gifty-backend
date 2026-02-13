from __future__ import annotations
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock
from routes.public import router, get_db, get_notification_service
from app.models import PartnerContact

@pytest.fixture
def db_mock():
    mock = AsyncMock()
    # Mocking the session behavior
    mock.add = MagicMock()
    mock.commit = AsyncMock()
    return mock

@pytest.fixture
def notifications_mock():
    return AsyncMock()

@pytest.fixture
def client(db_mock, notifications_mock):
    app = FastAPI()
    app.include_router(router)
    
    # Overriding dependencies for the router
    app.dependency_overrides[get_db] = lambda: db_mock
    app.dependency_overrides[get_notification_service] = lambda: notifications_mock
    
    return TestClient(app)

def test_partner_contact_happy_path(client, db_mock, notifications_mock):
    payload = {
        "name": "Test User",
        "company": "Test Co",
        "email": "test@example.com",
        "website": "https://example.com",
        "message": "Hello, I want to be a partner!",
        "hp": ""
    }
    response = client.post("/api/v1/public/partner-contact", json=payload)
    
    assert response.status_code == 201
    assert response.json() == {"ok": True}
    
    # Verify DB call
    db_mock.add.assert_called_once()
    # Check that it's a PartnerContact object
    added_obj = db_mock.add.call_args[0][0]
    assert isinstance(added_obj, PartnerContact)
    assert added_obj.name == "Test User"
    assert added_obj.email == "test@example.com"
    
    db_mock.commit.assert_called_once()
    
    # Verify notification call
    notifications_mock.notify.assert_called_once()
    args, kwargs = notifications_mock.notify.call_args
    assert kwargs["topic"] == "partners"
    assert "Test User" in kwargs["message"]

def test_partner_contact_honeypot(client, db_mock, notifications_mock):
    payload = {
        "name": "Bot User",
        "company": "Bot Co",
        "email": "bot@example.com",
        "message": "I am definitely a human being.",
        "hp": "spambot"
    }
    response = client.post("/api/v1/public/partner-contact", json=payload)
    
    assert response.status_code == 201  # Honeypot returns success to deceptive bots
    assert response.json() == {"ok": True}
    
    # Verify NO DB call and NO notification
    db_mock.add.assert_not_called()
    notifications_mock.notify.assert_not_called()

def test_partner_contact_validation_short_message(client):
    payload = {
        "name": "Test User",
        "email": "test@example.com",
        "message": "too short",
        "hp": ""
    }
    # min_length is 10
    response = client.post("/api/v1/public/partner-contact", json=payload)
    
    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any("message" in e["loc"] for e in errors)

def test_partner_contact_validation_invalid_email(client):
    payload = {
        "name": "Test User",
        "email": "invalid-email",
        "message": "This is a long enough message for testing.",
        "hp": ""
    }
    response = client.post("/api/v1/public/partner-contact", json=payload)
    
    assert response.status_code == 422

def test_partner_contact_metadata(client, db_mock):
    payload = {
        "name": "Meta User",
        "email": "meta@example.com",
        "message": "Testing IP and User Agent capture.",
        "hp": ""
    }
    headers = {"User-Agent": "TestAgent/1.0"}
    
    # TestClient by default sets host to 'testserver'
    response = client.post("/api/v1/public/partner-contact", json=payload, headers=headers)
    
    assert response.status_code == 201
    added_obj = db_mock.add.call_args[0][0]
    assert added_obj.user_agent == "TestAgent/1.0"
    # TestClient doesn't easily mock request.client.host without more complex setup, 
    # but we can verify the attribute exists.
