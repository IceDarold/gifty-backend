from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services import session_storage as storage_mod
from recommendations.models import RecommendationSession


class _FakeConn:
    def __init__(self):
        self.kv = {}
        self.setex = AsyncMock(side_effect=self._setex)
        self.get = AsyncMock(side_effect=self._get)
        self.delete = AsyncMock(side_effect=self._delete)

    async def _setex(self, key, ttl, value):
        self.kv[key] = value
        return True

    async def _get(self, key):
        return self.kv.get(key)

    async def _delete(self, key):
        self.kv.pop(key, None)
        return 1


@pytest.mark.asyncio
async def test_session_storage_save_get_delete_with_fake_redis(monkeypatch):
    fake_conn = _FakeConn()
    fake_fakeredis = _FakeConn()

    # Ensure fakeredis import path exists for the dev fallback branch.
    sys.modules["fakeredis"] = SimpleNamespace(aioredis=SimpleNamespace(FakeRedis=lambda decode_responses=True: fake_fakeredis))
    sys.modules["fakeredis.aioredis"] = SimpleNamespace(FakeRedis=lambda decode_responses=True: fake_fakeredis)

    monkeypatch.setattr(storage_mod, "get_settings", lambda: SimpleNamespace(redis_url="redis://", session_ttl_seconds=10, env="dev"), raising=True)
    monkeypatch.setattr(storage_mod.aioredis, "from_url", lambda *args, **kwargs: fake_conn, raising=True)

    storage = storage_mod.SessionStorage()
    # Force to use primary conn first
    storage.fake_redis = None

    session = RecommendationSession(
        session_id="s",
        recipient={"id": "r1", "name": None},
        full_recipient={"id": "r1", "findings": [], "interactions": [], "liked_hypotheses": [], "liked_labels": [], "ignored_hypotheses": [], "ignored_labels": [], "shortlist": []},
    )
    await storage.save_session(session)
    loaded = await storage.get_session("s")
    assert loaded is not None

    await storage.delete_session("s")
    assert await storage.get_session("s") is None


@pytest.mark.asyncio
async def test_session_storage_save_falls_back_to_fakeredis(monkeypatch):
    fake_conn = _FakeConn()
    fake_conn.setex = AsyncMock(side_effect=RuntimeError("down"))
    fake_fakeredis = _FakeConn()

    sys.modules["fakeredis"] = SimpleNamespace(aioredis=SimpleNamespace(FakeRedis=lambda decode_responses=True: fake_fakeredis))
    sys.modules["fakeredis.aioredis"] = SimpleNamespace(FakeRedis=lambda decode_responses=True: fake_fakeredis)

    monkeypatch.setattr(storage_mod, "get_settings", lambda: SimpleNamespace(redis_url="redis://", session_ttl_seconds=10, env="dev"), raising=True)
    monkeypatch.setattr(storage_mod.aioredis, "from_url", lambda *args, **kwargs: fake_conn, raising=True)

    storage = storage_mod.SessionStorage()
    storage.fake_redis = None

    session = RecommendationSession(
        session_id="s",
        recipient={"id": "r1", "name": None},
        full_recipient={"id": "r1", "findings": [], "interactions": [], "liked_hypotheses": [], "liked_labels": [], "ignored_hypotheses": [], "ignored_labels": [], "shortlist": []},
    )
    await storage.save_session(session)
    assert storage.fake_redis is not None
    assert "rec_session:s" in storage.fake_redis.kv
