from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.auth import routes as auth_routes


class _Scalars:
    def __init__(self, first_item):
        self._first = first_item

    def first(self):
        return self._first


class _Result:
    def __init__(self, first_item):
        self._first_item = first_item

    def scalars(self):
        return _Scalars(self._first_item)


@pytest.mark.anyio
async def test_upsert_user_updates_existing_account_and_user_fields():
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.add = lambda _obj: None
    db.flush = AsyncMock()

    user = SimpleNamespace(id=1, name="Old", email=None, avatar_url=None)
    account = SimpleNamespace(user=user)
    db.execute = AsyncMock(return_value=_Result(account))

    profile = SimpleNamespace(provider_user_id="p1", name="New", email="e@example.com", avatar_url="a")
    tokens = SimpleNamespace(access_token="t", refresh_token="r", expires_at=None)

    out = await auth_routes._upsert_user(db, "google", profile, tokens)
    assert out is user
    assert user.name == "New"
    assert user.email == "e@example.com"
    assert user.avatar_url == "a"


@pytest.mark.anyio
async def test_upsert_user_creates_new_user_and_account_when_missing():
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.add = lambda _obj: None
    db.flush = AsyncMock()
    db.execute = AsyncMock(return_value=_Result(None))

    profile = SimpleNamespace(provider_user_id="p1", name="Name", email="e@example.com", avatar_url=None)
    tokens = SimpleNamespace(access_token="t", refresh_token=None, expires_at=None)

    out = await auth_routes._upsert_user(db, "google", profile, tokens)
    assert out.name == "Name"
    assert out.email == "e@example.com"
