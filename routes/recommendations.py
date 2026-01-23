import uuid
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, status, HTTPException, Request
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.auth import session_store
from app.config import get_settings
from app.db import get_db
from app.models import User
from app.redis_client import get_redis
from app.schemas_v2 import RecommendationRequest, RecommendationResponse
from app.services.recommendation import RecommendationService
from repositories.recommendations import (
    create_quiz_run,
    log_event,
)

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/recommendations", tags=["recommendations"])

async def get_optional_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> Optional[User]:
    session_id = request.cookies.get(settings.session_cookie_name)
    if not session_id:
        return None
    session_data = await session_store.get_session(redis, session_id)
    if not session_data:
        return None
    try:
        user_id = uuid.UUID(session_data.get("user_id"))
    except Exception:
        return None

    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


def get_anon_id(request: Request) -> Optional[str]:
    return request.cookies.get("anon_id") or request.headers.get("X-Anon-Id")


@router.post(
    "/generate",
    response_model=RecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate recommendations from quiz answers",
)
async def generate_recommendations(
    payload: RecommendationRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
    anon_id: Optional[str] = Depends(get_anon_id),
) -> RecommendationResponse:
    # 1. Create Quiz Run
    quiz_run = await create_quiz_run(
        db,
        user_id=user.id if user else None,
        anon_id=anon_id,
        answers_json=payload.model_dump(),
    )

    # 2. Log event
    await log_event(
        db,
        "quiz_submitted",
        user_id=user.id if user else None,
        anon_id=anon_id,
        quiz_run_id=quiz_run.id,
        payload=payload.model_dump(),
    )

    # 3. Use RecommendationService
    embedding_service = request.app.state.embedding_service
    service = RecommendationService(db, embedding_service)
    response = await service.generate_recommendations(payload)
    
    # Update quiz_run_id in response
    response.quiz_run_id = str(quiz_run.id)

    return response
