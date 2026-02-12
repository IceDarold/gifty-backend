from __future__ import annotations

from fastapi import Request
from redis.asyncio import Redis, from_url

from app.config import get_settings

settings = get_settings()


async def init_redis() -> Redis:
    return from_url(settings.redis_url, decode_responses=True)


async def get_redis(request: Request) -> Redis:
    redis: Redis = request.app.state.redis
    return redis

