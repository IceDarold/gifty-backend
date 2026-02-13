from __future__ import annotations
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock
from routes.public import router, get_db, get_redis, get_notification_service
from app.models import InvestorContact

@pytest.fixture
def db_mock():
    mock = AsyncMock()
    mock.add = MagicMock()
    mock.commit = AsyncMock()
    # Mocking the execute for double check (select existing)
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    mock.execute = AsyncMock(return_value=result_mock)
    return mock

@pytest.fixture
def redis_mock():
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.incr = AsyncMock(return_value=1)
    mock.expire = AsyncMock()
    return mock

@pytest.fixture
def notifications_mock():
    return AsyncMock()

@pytest.fixture
def client(db_mock, redis_mock, notifications_mock):
    app = FastAPI()
    app.include_router(router)
    
    app.dependency_overrides[get_db] = lambda: db_mock
    app.dependency_overrides[get_redis] = lambda: redis_mock
    app.dependency_overrides[get_notification_service] = lambda: notifications_mock
    
    return TestClient(app)

def test_investor_contact_happy_path(client, db_mock, redis_mock, notifications_mock):
    payload = {
        "name": "John Investor",
        "company": "VC Firm",
        "email": "john@vcfirm.com",
        "linkedin": "https://linkedin.com/in/john",
        "hp": ""
    }
    response = client.post("/api/v1/public/investor-contact", json=payload)
    
    assert response.status_code == 201
    assert response.json() == {"ok": True}
    
    # 1. Check DB save
    db_mock.add.assert_called_once()
    added_obj = db_mock.add.call_args[0][0]
    assert isinstance(added_obj, InvestorContact)
    assert added_obj.name == "John Investor"
    assert added_obj.email == "john@vcfirm.com"
    db_mock.commit.assert_called_once()
    
    # 2. Check Redis (rate limit)
    redis_mock.get.assert_called_once()
    redis_mock.incr.assert_called_once()
    
    # 3. Check Notification
    notifications_mock.notify.assert_called_once()
    _, kwargs = notifications_mock.notify.call_args
    assert kwargs["topic"] == "investors"
    assert "John Investor" in kwargs["message"]

def test_investor_contact_honeypot(client, db_mock, notifications_mock):
    payload = {
        "name": "Bot",
        "email": "bot@spam.com",
        "hp": "fillme"
    }
    response = client.post("/api/v1/public/investor-contact", json=payload)
    
    assert response.status_code == 201 # Honeypot returns 201 via decorator
    db_mock.add.assert_not_called()
    notifications_mock.notify.assert_not_called()

def test_investor_contact_rate_limit(client, redis_mock, db_mock):
    # Mock redis to return 5 (limit exceeded)
    redis_mock.get.return_value = "5"
    
    payload = {
        "name": "Spammer",
        "email": "spam@example.com",
        "hp": ""
    }
    response = client.post("/api/v1/public/investor-contact", json=payload)
    
    assert response.status_code == 429
    assert "Too many requests" in response.json()["detail"]["message"]
    db_mock.add.assert_not_called()

def test_investor_contact_duplicate_prevention(client, db_mock):
    # Mock DB to return an existing record
    db_mock.execute.return_value.scalar_one_or_none.return_value = MagicMock()
    
    payload = {
        "name": "Repeat Customer",
        "email": "repeat@example.com",
        "hp": ""
    }
    response = client.post("/api/v1/public/investor-contact", json=payload)
    
    assert response.status_code == 201
    assert response.json() == {"ok": True}
    # Should NOT call add or commit because it's a "silent" duplicate ignore
    db_mock.add.assert_not_called()

def test_investor_contact_validation_errors(client):
    # 1. Invalid Email
    response = client.post("/api/v1/public/investor-contact", json={
        "name": "Shorty",
        "email": "not-an-email",
        "hp": ""
    })
    assert response.status_code == 422
    
    # 2. Name too short
    response = client.post("/api/v1/public/investor-contact", json={
        "name": "A",
        "email": "test@test.com",
        "hp": ""
    })
    assert response.status_code == 422
