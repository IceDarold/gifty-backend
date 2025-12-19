import json
from typing import Any, Dict, Optional

from redis.asyncio import Redis


STATE_KEY_PREFIX = "oauth_state:"


async def save_state(redis: Redis, state: str, payload: Dict[str, Any], ttl_seconds: int) -> None:
    key = f"{STATE_KEY_PREFIX}{state}"
    await redis.set(key, json.dumps(payload), ex=ttl_seconds)


async def get_state(redis: Redis, state: str) -> Optional[Dict[str, Any]]:
    key = f"{STATE_KEY_PREFIX}{state}"
    raw = await redis.get(key)
    if not raw:
        return None
    return json.loads(raw)


async def pop_state(redis: Redis, state: str) -> Optional[Dict[str, Any]]:
    key = f"{STATE_KEY_PREFIX}{state}"
    pipeline = redis.pipeline()
    pipeline.get(key)
    pipeline.delete(key)
    raw, _ = await pipeline.execute()
    if not raw:
        return None
    return json.loads(raw)
