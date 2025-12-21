from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from models import Event, QuizRun, RecommendationRun


async def create_quiz_run(
    db: AsyncSession,
    *,
    user_id: Optional[UUID],
    anon_id: Optional[str],
    answers_json: dict[str, Any],
) -> QuizRun:
    quiz_run = QuizRun(user_id=user_id, anon_id=anon_id, answers_json=answers_json)
    db.add(quiz_run)
    await db.commit()
    await db.refresh(quiz_run)
    return quiz_run


async def create_recommendation_run(
    db: AsyncSession,
    *,
    quiz_run_id: UUID,
    engine_version: str,
    featured_gift_id: str,
    gift_ids: list[str],
    debug_json: Optional[dict[str, Any]] = None,
) -> RecommendationRun:
    recommendation_run = RecommendationRun(
        quiz_run_id=quiz_run_id,
        engine_version=engine_version,
        featured_gift_id=featured_gift_id,
        gift_ids=gift_ids,
        debug_json=debug_json,
    )
    db.add(recommendation_run)
    await db.commit()
    await db.refresh(recommendation_run)
    return recommendation_run


async def log_event(
    db: AsyncSession,
    event_name: str,
    *,
    user_id: Optional[UUID] = None,
    anon_id: Optional[str] = None,
    quiz_run_id: Optional[UUID] = None,
    recommendation_run_id: Optional[UUID] = None,
    gift_id: Optional[str] = None,
    payload: Optional[dict[str, Any]] = None,
) -> None:
    event = Event(
        event_name=event_name,
        user_id=user_id,
        anon_id=anon_id,
        quiz_run_id=quiz_run_id,
        recommendation_run_id=recommendation_run_id,
        gift_id=gift_id,
        payload=payload,
    )
    db.add(event)
    await db.commit()
