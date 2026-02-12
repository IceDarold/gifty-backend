import asyncio
from fakeredis.aioredis import FakeRedis

from app.auth import state_store


def test_state_round_trip():
    async def _run():
        redis = FakeRedis(decode_responses=True)
        await state_store.save_state(redis, "abc", {"foo": "bar"}, ttl_seconds=10)

        stored = await state_store.get_state(redis, "abc")
        assert stored == {"foo": "bar"}

        popped = await state_store.pop_state(redis, "abc")
        assert popped == {"foo": "bar"}

        missing = await state_store.get_state(redis, "abc")
        assert missing is None

        await redis.close()

    asyncio.run(_run())

