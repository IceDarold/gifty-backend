from __future__ import annotations

import uuid
import pytest
from sqlalchemy import select

from recommendations.models import RecipientProfile, QuizAnswers, UserInteraction, Hypothesis as RecHypothesis
from app.models import Recipient, Interaction, Hypothesis


@pytest.mark.asyncio
async def test_create_recipient_persists(recipient_service, sqlite_db_session):
    quiz = QuizAnswers(interests=["Кофе"], recipient_age=30)
    profile = RecipientProfile(quiz_data=quiz)
    user_id = uuid.uuid4()

    created = await recipient_service.create_recipient(user_id=user_id, profile=profile)

    db_recipient = await sqlite_db_session.execute(
        select(Recipient).where(Recipient.id == created.id)
    )
    found = db_recipient.scalar_one_or_none()
    assert found is not None
    assert found.user_id == user_id
    assert found.interests == ["Кофе"]


@pytest.mark.asyncio
async def test_get_and_update_recipient(recipient_service, sqlite_db_session):
    quiz = QuizAnswers(interests=["Книги"], recipient_age=25)
    profile = RecipientProfile(quiz_data=quiz, name="Initial")
    created = await recipient_service.create_recipient(user_id=None, profile=profile)

    fetched = await recipient_service.get_recipient(created.id)
    assert fetched is not None
    assert fetched.name == "Initial"

    updated = await recipient_service.update_recipient(
        recipient_id=created.id,
        name="Updated",
        interests=["Книги", "Кофе"],
    )
    assert updated is not None
    assert updated.name == "Updated"
    assert updated.interests == ["Книги", "Кофе"]


@pytest.mark.asyncio
async def test_get_user_recipients_ordering(recipient_service):
    user_id = uuid.uuid4()
    quiz = QuizAnswers(interests=["A"], recipient_age=20)
    profile1 = RecipientProfile(quiz_data=quiz, name="First")
    profile2 = RecipientProfile(quiz_data=quiz, name="Second")

    await recipient_service.create_recipient(user_id=user_id, profile=profile1)
    await recipient_service.create_recipient(user_id=user_id, profile=profile2)

    recipients = await recipient_service.get_user_recipients(user_id=user_id)
    assert len(recipients) == 2
    assert recipients[0].created_at >= recipients[1].created_at


@pytest.mark.asyncio
async def test_save_hypotheses_persists(recipient_service, sqlite_db_session):
    quiz = QuizAnswers(interests=["Кофе"], recipient_age=30)
    profile = RecipientProfile(quiz_data=quiz)
    recipient = await recipient_service.create_recipient(user_id=None, profile=profile)

    hypo = RecHypothesis(
        id=str(uuid.uuid4()),
        title="Набор для альтернативного заваривания",
        description="Описание",
        reasoning="Обоснование",
        primary_gap="the_optimizer",
        search_queries=["aeropress", "v60"],
    )

    saved = await recipient_service.save_hypotheses(
        session_id="session-1",
        recipient_id=recipient.id,
        track_title="Кофе",
        hypotheses=[hypo],
    )

    assert saved
    db_h = await sqlite_db_session.execute(
        select(Hypothesis).where(Hypothesis.id == uuid.UUID(hypo.id))
    )
    found = db_h.scalar_one_or_none()
    assert found is not None
    assert found.track_title == "Кофе"
    assert found.search_queries == ["aeropress", "v60"]


@pytest.mark.asyncio
async def test_interaction_and_reaction_persist(recipient_service, sqlite_db_session):
    quiz = QuizAnswers(interests=["Кофе"], recipient_age=30)
    profile = RecipientProfile(quiz_data=quiz)
    recipient = await recipient_service.create_recipient(user_id=None, profile=profile)

    hypo = RecHypothesis(
        id=str(uuid.uuid4()),
        title="Кофе-подписка",
        description="Описание",
        reasoning="Обоснование",
        primary_gap="the_mirror",
        search_queries=["coffee subscription"],
    )
    await recipient_service.save_hypotheses(
        session_id="session-2",
        recipient_id=recipient.id,
        track_title="Кофе",
        hypotheses=[hypo],
    )

    interaction = UserInteraction(
        type="like_hypothesis",
        timestamp=123.0,
        target_id=hypo.id,
        target_type="hypothesis",
        value=None,
        metadata={"source": "test"},
    )

    saved_interaction = await recipient_service.save_interaction(
        recipient_id=recipient.id,
        session_id="session-2",
        interaction=interaction,
    )

    db_i = await sqlite_db_session.execute(
        select(Interaction).where(Interaction.id == saved_interaction.id)
    )
    found_i = db_i.scalar_one_or_none()
    assert found_i is not None
    assert found_i.action_type == "like_hypothesis"

    updated = await recipient_service.update_hypothesis_reaction(
        hypothesis_id=uuid.UUID(hypo.id),
        reaction="like",
    )
    assert updated is not None
    assert updated.user_reaction == "like"


@pytest.mark.asyncio
async def test_get_hypothesis_and_missing_cases(recipient_service, sqlite_db_session):
    quiz = QuizAnswers(interests=["Кофе"], recipient_age=30)
    profile = RecipientProfile(quiz_data=quiz)
    recipient = await recipient_service.create_recipient(user_id=None, profile=profile)

    hypo = RecHypothesis(
        id=str(uuid.uuid4()),
        title="Кофе-дегустация",
        description="Описание",
        reasoning="Обоснование",
        primary_gap="the_anchor",
        search_queries=["coffee tasting"],
    )
    await recipient_service.save_hypotheses(
        session_id="session-3",
        recipient_id=recipient.id,
        track_title="Кофе",
        hypotheses=[hypo],
    )

    found = await recipient_service.get_hypothesis(uuid.UUID(hypo.id))
    assert found is not None
    assert found.title == "Кофе-дегустация"

    missing = await recipient_service.get_hypothesis(uuid.uuid4())
    assert missing is None

    missing_update = await recipient_service.update_hypothesis_reaction(uuid.uuid4(), "like")
    assert missing_update is None


@pytest.mark.asyncio
async def test_get_recipient_interactions(recipient_service, sqlite_db_session):
    quiz = QuizAnswers(interests=["Кофе"], recipient_age=30)
    profile = RecipientProfile(quiz_data=quiz)
    recipient = await recipient_service.create_recipient(user_id=None, profile=profile)

    interaction = UserInteraction(
        type="view",
        timestamp=1.0,
        target_id="x",
        target_type="hypothesis",
        value=None,
        metadata={"k": "v"},
    )
    await recipient_service.save_interaction(
        recipient_id=recipient.id,
        session_id="session-4",
        interaction=interaction,
    )

    interactions = await recipient_service.get_recipient_interactions(recipient.id, limit=10)
    assert len(interactions) == 1
    assert interactions[0].action_type == "view"
