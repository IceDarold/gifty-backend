from __future__ import annotations

import hashlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from routes import internal as internal_routes
from tests.routes.internal.conftest import assert_ok


@pytest.fixture
def telegram_repo(monkeypatch):
    repo = SimpleNamespace(
        get_all_subscribers=AsyncMock(return_value=[{"chat_id": 1}]),
        get_subscriber=AsyncMock(return_value={"chat_id": 1, "role": "admin", "permissions": []}),
        get_subscriber_by_slug=AsyncMock(return_value=None),
        get_subscriber_by_id=AsyncMock(return_value={"chat_id": 99}),
        create_subscriber=AsyncMock(return_value={"chat_id": 2}),
        create_invite=AsyncMock(return_value={"slug": "u"}),
        claim_invite=AsyncMock(return_value={"chat_id": 3, "role": "admin", "permissions": []}),
        set_role=AsyncMock(return_value=True),
        set_permissions=AsyncMock(return_value=True),
        subscribe_topic=AsyncMock(return_value=True),
        unsubscribe_topic=AsyncMock(return_value=True),
        get_subscribers_for_topic=AsyncMock(return_value=[{"chat_id": 1}]),
        set_language=AsyncMock(return_value=True),
    )
    monkeypatch.setattr(internal_routes, "TelegramRepository", lambda db: repo, raising=True)
    return repo


def test_hash_invite_password_uses_secret(monkeypatch):
    monkeypatch.setattr(internal_routes.settings, "secret_key", "s3cr3t")
    out = internal_routes._hash_invite_password("pw")
    expected = hashlib.sha256(b"s3cr3t:pw").hexdigest()
    assert out == expected


def test_list_and_get_subscribers(client, telegram_repo):
    resp = client.get("/api/v1/internal/telegram/subscribers")
    assert resp.status_code == 200

    resp2 = client.get("/api/v1/internal/telegram/subscribers/1")
    assert resp2.status_code == 200


def test_get_subscriber_by_username_normalizes(client, telegram_repo):
    telegram_repo.get_subscriber_by_slug = AsyncMock(return_value={"chat_id": 1, "slug": "user"})
    resp = client.get("/api/v1/internal/telegram/subscribers/by-username/@User")
    assert resp.status_code == 200
    telegram_repo.get_subscriber_by_slug.assert_awaited_with("user")


def test_create_invite_validation_and_conflict(client, telegram_repo):
    resp = client.post("/api/v1/internal/telegram/invites", json={"username": "   ", "password": "pw"})
    assert resp.status_code == 400

    telegram_repo.get_subscriber_by_slug = AsyncMock(return_value={"chat_id": 1})
    resp2 = client.post("/api/v1/internal/telegram/invites", json={"username": "u", "password": "pw"})
    assert resp2.status_code == 409


def test_create_invite_mentor_not_found(client, telegram_repo):
    telegram_repo.get_subscriber_by_slug = AsyncMock(return_value=None)
    telegram_repo.get_subscriber_by_id = AsyncMock(return_value=None)
    resp = client.post("/api/v1/internal/telegram/invites", json={"username": "u", "password": "pw", "mentor_id": 123})
    assert resp.status_code == 400


def test_create_and_claim_invite(client, telegram_repo):
    telegram_repo.get_subscriber_by_slug = AsyncMock(return_value=None)
    telegram_repo.get_subscriber_by_id = AsyncMock(return_value={"chat_id": 9})
    resp = client.post("/api/v1/internal/telegram/invites", json={"username": "u", "password": "pw", "mentor_id": 1})
    assert resp.status_code == 200

    telegram_repo.claim_invite = AsyncMock(return_value=None)
    resp2 = client.post("/api/v1/internal/telegram/invites/claim", json={"username": "u", "password": "pw", "chat_id": 1})
    assert resp2.status_code == 404

    telegram_repo.claim_invite = AsyncMock(return_value={"chat_id": 1})
    resp3 = client.post("/api/v1/internal/telegram/invites/claim", json={"username": "u", "password": "pw", "chat_id": 1})
    assert resp3.status_code == 200


def test_role_and_permissions(client, telegram_repo):
    resp = client.post("/api/v1/internal/telegram/subscribers/1/role", params={"role": "admin"})
    assert_ok(resp)

    resp2 = client.post("/api/v1/internal/telegram/subscribers/1/permissions", json=["x", "y"])
    assert_ok(resp2)


def test_subscribe_unsubscribe_language_topic_subscribers(client, telegram_repo):
    resp = client.post("/api/v1/internal/telegram/subscribers/1/subscribe", params={"topic": "all"})
    assert_ok(resp)
    resp2 = client.post("/api/v1/internal/telegram/subscribers/1/unsubscribe", params={"topic": "all"})
    assert_ok(resp2)
    resp3 = client.get("/api/v1/internal/telegram/topics/all/subscribers")
    assert resp3.status_code == 200
    resp4 = client.post("/api/v1/internal/telegram/subscribers/1/language", params={"language": "ru"})
    assert_ok(resp4)

