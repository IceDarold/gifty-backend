from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import Request

from app.auth import deps
from app.utils.errors import AppError


class _Result:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


@pytest.mark.asyncio
async def test_get_current_user_missing_cookie():
    scope = {"type": "http", "headers": [], "path": "/"}
    req = Request(scope)
    with pytest.raises(AppError) as exc:
        await deps.get_current_user(req, db=AsyncMock(), redis=AsyncMock())
    assert exc.value.http_status == 401


@pytest.mark.asyncio
async def test_get_current_user_invalid_session(monkeypatch):
    scope = {"type": "http", "headers": [], "path": "/"}
    req = Request(scope)
    req._cookies = {deps.settings.session_cookie_name: "s1"}  # type: ignore[attr-defined]

    monkeypatch.setattr(deps.session_store, "get_session", AsyncMock(return_value=None))
    with pytest.raises(AppError) as exc:
        await deps.get_current_user(req, db=AsyncMock(), redis=AsyncMock())
    assert exc.value.http_status == 401


@pytest.mark.asyncio
async def test_get_current_user_happy(monkeypatch):
    user_id = str(uuid.uuid4())
    scope = {"type": "http", "headers": [], "path": "/"}
    req = Request(scope)
    req._cookies = {deps.settings.session_cookie_name: "s1"}  # type: ignore[attr-defined]

    monkeypatch.setattr(deps.session_store, "get_session", AsyncMock(return_value={"user_id": user_id}))

    db = AsyncMock()
    db.execute = AsyncMock(return_value=_Result(SimpleNamespace(id=uuid.UUID(user_id))))

    user = await deps.get_current_user(req, db=db, redis=AsyncMock())
    assert str(user.id) == user_id

