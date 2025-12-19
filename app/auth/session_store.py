import json
from typing import Any, Dict, Optional

from redis.asyncio import Redis

SESSION_KEY_PREFIX = "sessions:"


async def create_session(redis: Redis, session_id: str, payload: Dict[str, Any], ttl_seconds: int) -> None:
    key = f"{SESSION_KEY_PREFIX}{session_id}"
    await redis.set(key, json.dumps(payload), ex=ttl_seconds)


async def get_session(redis: Redis, session_id: str) -> Optional[Dict[str, Any]]:
    key = f"{SESSION_KEY_PREFIX}{session_id}"
    raw = await redis.get(key)
    if not raw:
        return None
    return json.loads(raw)


async def delete_session(redis: Redis, session_id: str) -> None:
    key = f"{SESSION_KEY_PREFIX}{session_id}"
    await redis.delete(key)
