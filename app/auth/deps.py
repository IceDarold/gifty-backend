from __future__ import annotations

import uuid

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.config import get_settings
from app.db import get_db
from app.models import User
from app.auth import session_store
from app.redis_client import get_redis
from app.utils.errors import AppError

settings = get_settings()


async def get_current_user(
    request: Request, db: AsyncSession = Depends(get_db), redis: Redis = Depends(get_redis)
) -> User:
    session_id = request.cookies.get(settings.session_cookie_name)
    if not session_id:
        raise AppError("unauthorized", "Authentication required", status.HTTP_401_UNAUTHORIZED)

    session_data = await session_store.get_session(redis, session_id)
    if not session_data:
        raise AppError("unauthorized", "Session is invalid or expired", status.HTTP_401_UNAUTHORIZED)

    try:
        user_id = uuid.UUID(session_data.get("user_id"))
    except Exception:
        raise AppError("unauthorized", "Session payload invalid", status.HTTP_401_UNAUTHORIZED)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise AppError("unauthorized", "User not found", status.HTTP_401_UNAUTHORIZED)
    return user

