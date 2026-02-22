from __future__ import annotations

import re
import uuid
import pytest
from sqlalchemy import select, func
from unittest.mock import AsyncMock

from app.services.dialogue_manager import DialogueManager
from app.models import Recipient, Hypothesis, Interaction
from recommendations.models import QuizAnswers

from .scenarios import get_scenarios


def _has_cyrillic(text: str) -> bool:
    if not text:
        return False
    return re.search(r"[А-Яа-я]", text) is not None


@pytest.mark.ai_test
@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", get_scenarios(), ids=lambda s: s.name)
async def test_llm_init_session_tracks(
    scenario,
    llm_reporter,
    timed_ai_service,
    in_memory_session_storage,
    sqlite_db_session,
    sqlite_recipient_service,
):
    llm_reporter.start_scenario(
        f"Init Session: {scenario.name}",
        {"quiz": scenario.quiz.model_dump()},
    )

    recommendation_service = AsyncMock()
    recommendation_service.find_preview_products.return_value = []
    user_id = uuid.uuid4()

    dm = DialogueManager(
        ai_service=timed_ai_service,
        recommendation_service=recommendation_service,
        session_storage=in_memory_session_storage,
        recipient_service=sqlite_recipient_service,
        db=sqlite_db_session,
    )

    session = await dm.init_session(scenario.quiz, user_id=user_id)
    llm_reporter.add_output("session.topics", session.topics)
    llm_reporter.add_output(
        "tracks.summary",
        [
            {
                "topic": t.topic_name,
                "status": t.status,
                "hypotheses": [h.title for h in t.hypotheses],
                "question": t.question.question if t.question else None,
                "question_options": t.question.options if t.question else [],
            }
            for t in session.tracks
        ],
    )

    has_tracks_or_probe = bool(session.tracks) or session.current_probe is not None
    llm_reporter.add_check(
        "session has tracks or probe",
        "pass" if has_tracks_or_probe else "fail",
    )

    if session.tracks:
        empty_titles = [h.title for t in session.tracks for h in t.hypotheses if not h.title]
        llm_reporter.add_check(
            "hypotheses have titles",
            "pass" if not empty_titles else "fail",
            detail=f"missing titles: {len(empty_titles)}" if empty_titles else None,
        )

        titles = [h.title for t in session.tracks for h in t.hypotheses]
        dup_titles = {t for t in titles if titles.count(t) > 1}
        llm_reporter.add_check(
            "no duplicate hypothesis titles",
            "pass" if not dup_titles else "warn",
            detail=f"duplicates: {sorted(dup_titles)}" if dup_titles else None,
        )

        ru_texts = [h.title for t in session.tracks for h in t.hypotheses]
        has_ru = any(_has_cyrillic(t) for t in ru_texts)
        llm_reporter.add_check(
            "RU language output",
            "pass" if has_ru else "warn",
        )

    # DB checks
    recipient_id = uuid.UUID(session.full_recipient.id)
    db_recipient = await sqlite_db_session.execute(
        select(Recipient).where(Recipient.id == recipient_id)
    )
    llm_reporter.add_check(
        "recipient persisted",
        "pass" if db_recipient.scalar_one_or_none() else "fail",
    )

    # hypotheses saved for ready tracks
    ready_hypotheses = [
        h for t in session.tracks if t.status == "ready" for h in t.hypotheses
    ]
    if ready_hypotheses:
        db_hypo_count = await sqlite_db_session.execute(
            select(func.count(Hypothesis.id)).where(Hypothesis.session_id == session.session_id)
        )
        count = db_hypo_count.scalar_one()
        llm_reporter.add_check(
            "hypotheses persisted",
            "pass" if count >= len(ready_hypotheses) else "warn",
            detail=f"db={count}, expected>={len(ready_hypotheses)}",
        )
    else:
        llm_reporter.add_check(
            "hypotheses persisted",
            "warn",
            detail="no ready hypotheses to persist",
        )


@pytest.mark.ai_test
@pytest.mark.asyncio
async def test_llm_classify_topic_wide(timed_ai_service, llm_reporter):
    quiz_data = QuizAnswers(interests=["Музыка"], recipient_age=30).model_dump()
    llm_reporter.start_scenario(
        "Classify Topic: Music",
        {"topic": "Музыка", "quiz": quiz_data},
    )

    result = await timed_ai_service.classify_topic("Музыка", quiz_data, language="ru")
    llm_reporter.add_output("classify_topic", result)

    is_wide = bool(result.get("is_wide"))
    llm_reporter.add_check("is_wide present", "pass" if "is_wide" in result else "fail")
    llm_reporter.add_check("wide topic likely", "pass" if is_wide else "warn")

    if is_wide:
        question = result.get("question")
        branches = result.get("branches", [])
        llm_reporter.add_check(
            "wide topic has question",
            "pass" if question else "fail",
        )
        llm_reporter.add_check(
            "wide topic has branches",
            "pass" if branches else "fail",
        )


@pytest.mark.ai_test
@pytest.mark.asyncio
async def test_llm_personalized_probe(timed_ai_service, llm_reporter):
    quiz_data = QuizAnswers(interests=["Винил"], recipient_age=45).model_dump()
    llm_reporter.start_scenario(
        "Personalized Probe: dead_end",
        {"context_type": "dead_end", "quiz": quiz_data},
    )

    probe = await timed_ai_service.generate_personalized_probe(
        context_type="dead_end",
        quiz_data=quiz_data,
        language="ru",
    )
    llm_reporter.add_output("probe", probe)

    has_question = bool(probe.get("question"))
    llm_reporter.add_check("probe has question", "pass" if has_question else "fail")


@pytest.mark.ai_test
@pytest.mark.asyncio
async def test_llm_topic_hints(timed_ai_service, llm_reporter):
    quiz_data = QuizAnswers(interests=["Кофе"], recipient_age=28).model_dump()
    llm_reporter.start_scenario(
        "Topic Hints",
        {"quiz": quiz_data, "topics_explored": ["Кофе"]},
    )

    hints = await timed_ai_service.generate_topic_hints(
        quiz_data=quiz_data,
        topics_explored=["Кофе"],
        language="ru",
    )
    llm_reporter.add_output("topic_hints", hints)

    llm_reporter.add_check("hints not empty", "pass" if hints else "warn")


@pytest.mark.ai_test
@pytest.mark.asyncio
async def test_llm_interaction_persists(
    llm_reporter,
    timed_ai_service,
    in_memory_session_storage,
    sqlite_db_session,
    sqlite_recipient_service,
):
    quiz = QuizAnswers(interests=["Кофе"], recipient_age=28)
    llm_reporter.start_scenario(
        "Interaction Persistence",
        {"quiz": quiz.model_dump()},
    )

    recommendation_service = AsyncMock()
    recommendation_service.get_deep_dive_products.return_value = []
    user_id = uuid.uuid4()

    dm = DialogueManager(
        ai_service=timed_ai_service,
        recommendation_service=recommendation_service,
        session_storage=in_memory_session_storage,
        recipient_service=sqlite_recipient_service,
        db=sqlite_db_session,
    )

    session = await dm.init_session(quiz, user_id=user_id)
    hypothesis = None
    for t in session.tracks:
        if t.hypotheses:
            hypothesis = t.hypotheses[0]
            break

    if not hypothesis:
        llm_reporter.add_check("interaction persisted", "warn", detail="no hypothesis to like")
        pytest.skip("No hypotheses to interact with")

    await dm.interact(session.session_id, "like_hypothesis", hypothesis.id)

    db_interactions = await sqlite_db_session.execute(
        select(Interaction).where(Interaction.session_id == session.session_id)
    )
    interaction = db_interactions.scalars().first()
    llm_reporter.add_check(
        "interaction persisted",
        "pass" if interaction else "fail",
    )

    db_hypo = await sqlite_db_session.execute(
        select(Hypothesis).where(Hypothesis.id == uuid.UUID(hypothesis.id))
    )
    db_h = db_hypo.scalar_one_or_none()
    llm_reporter.add_check(
        "hypothesis reaction updated",
        "pass" if db_h and db_h.user_reaction == "like" else "warn",
        detail=f"reaction={db_h.user_reaction if db_h else None}",
    )
