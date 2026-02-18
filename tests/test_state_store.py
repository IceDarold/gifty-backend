import pytest
from fakeredis.aioredis import FakeRedis

from app.auth import state_store


@pytest.mark.asyncio
async def test_state_round_trip():
    redis = FakeRedis(decode_responses=True)
    try:
        await state_store.save_state(redis, "abc", {"foo": "bar"}, ttl_seconds=10)

        stored = await state_store.get_state(redis, "abc")
        assert stored == {"foo": "bar"}

        popped = await state_store.pop_state(redis, "abc")
        assert popped == {"foo": "bar"}

        missing = await state_store.get_state(redis, "abc")
        assert missing is None
    finally:
        await redis.aclose()
