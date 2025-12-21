from __future__ import annotations

import uuid
from typing import Any, Optional

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.auth import session_store
from app.config import get_settings
from app.db import get_db
from app.models import User
from app.redis_client import get_redis
from app.utils.errors import AppError
from recommendations.candidate_collector import collect_candidates
from recommendations.models import QuizAnswers
from recommendations.query_rules_loader import load_ruleset
from recommendations.query_generator import generate_queries
from recommendations.ranker_v1 import RankingResult, rank_candidates
from repositories.recommendations import (
    create_quiz_run,
    create_recommendation_run,
    log_event,
)

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/recommendations", tags=["recommendations"])
_RULESET_PATH = "config/gift_query_rules.v1.yaml"


class RecommendationRequest(BaseModel):
    recipient_age: int
    relationship: Optional[str] = None
    occasion: Optional[str] = None
    vibe: Optional[str] = None
    interests: list[str] = Field(default_factory=list)
    interests_description: Optional[str] = None
    budget: Optional[int] = None
    city: Optional[str] = None
    debug: bool = False


class RecommendationResponse(BaseModel):
    quiz_run_id: str
    engine_version: str
    featured_gift_id: str
    gift_ids: list[str]
    debug: Optional[dict[str, Any]] = None


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
    responses={
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "No candidates found",
            "content": {
                "application/json": {
                    "example": {"error": {"code": "no_candidates_found", "message": "No candidates found"}}
                }
            },
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal error",
            "content": {
                "application/json": {
                    "example": {"error": {"code": "internal_error", "message": "Unexpected error"}}
                }
            },
        },
    },
)
async def generate_recommendations(
    payload: RecommendationRequest,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
    anon_id: Optional[str] = Depends(get_anon_id),
) -> RecommendationResponse:
    quiz = QuizAnswers(**payload.model_dump(exclude={"city", "debug"}))

    quiz_run = await create_quiz_run(
        db,
        user_id=user.id if user else None,
        anon_id=anon_id,
        answers_json=payload.model_dump(),
    )

    ruleset = load_ruleset(_RULESET_PATH)
    queries = generate_queries(quiz, ruleset)
    if not queries:
        raise AppError("no_candidates_found", "No candidates found", status.HTTP_422_UNPROCESSABLE_ENTITY)

    candidates, collector_debug = collect_candidates(queries)
    if not candidates:
        raise AppError("no_candidates_found", "No candidates found", status.HTTP_422_UNPROCESSABLE_ENTITY)

    ranking_result: RankingResult = rank_candidates(quiz, candidates, debug=payload.debug)

    await log_event(
        db,
        "quiz_submitted",
        user_id=user.id if user else None,
        anon_id=anon_id,
        quiz_run_id=quiz_run.id,
        payload=payload.model_dump(),
    )

    recommendation_run = await create_recommendation_run(
        db,
        quiz_run_id=quiz_run.id,
        engine_version=ranking_result.engine_version,
        featured_gift_id=ranking_result.featured_gift_id,
        gift_ids=ranking_result.gift_ids,
        debug_json=ranking_result.debug,
    )

    await log_event(
        db,
        "recommendations_generated",
        user_id=user.id if user else None,
        anon_id=anon_id,
        quiz_run_id=quiz_run.id,
        recommendation_run_id=recommendation_run.id,
        payload={"engine_version": ranking_result.engine_version},
    )

    debug_payload: Optional[dict[str, Any]] = None
    if payload.debug:
        debug_payload = {
            "queries": queries,
            "candidate_collector": collector_debug,
            "ranker": ranking_result.debug,
        }
    logger.info(
        "debug_requested=%s debug_returned=%s",
        payload.debug,
        debug_payload is not None,
    )

    return RecommendationResponse(
        quiz_run_id=str(quiz_run.id),
        engine_version=ranking_result.engine_version,
        featured_gift_id=ranking_result.featured_gift_id,
        gift_ids=ranking_result.gift_ids,
        debug=debug_payload,
    )
