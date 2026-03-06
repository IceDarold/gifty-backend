from __future__ import annotations

import json
import pytest

from app.auth import session_store, state_store


class FakePipeline:
    def __init__(self, redis: "FakeRedis"):
        self._redis = redis
        self._ops = []

    def get(self, key: str):
        self._ops.append(("get", key))
        return self

    def delete(self, key: str):
        self._ops.append(("del", key))
        return self

    async def execute(self):
        out = []
        for op, key in self._ops:
            if op == "get":
                out.append(await self._redis.get(key))
            else:
                out.append(await self._redis.delete(key))
        return out


class FakeRedis:
    def __init__(self):
        self._kv = {}

    async def set(self, key, value, ex=None):
        self._kv[key] = value
        return True

    async def get(self, key):
        return self._kv.get(key)

    async def delete(self, key):
        self._kv.pop(key, None)
        return 1

    def pipeline(self):
        return FakePipeline(self)


@pytest.mark.asyncio
async def test_state_store_save_get_pop():
    r = FakeRedis()
    await state_store.save_state(r, "s", {"a": 1}, ttl_seconds=10)
    got = await state_store.get_state(r, "s")
    assert got == {"a": 1}
    popped = await state_store.pop_state(r, "s")
    assert popped == {"a": 1}
    assert await state_store.get_state(r, "s") is None


@pytest.mark.asyncio
async def test_session_store_crud():
    r = FakeRedis()
    await session_store.create_session(r, "id1", {"u": "1"}, ttl_seconds=10)
    got = await session_store.get_session(r, "id1")
    assert got == {"u": "1"}
    await session_store.delete_session(r, "id1")
    assert await session_store.get_session(r, "id1") is None

