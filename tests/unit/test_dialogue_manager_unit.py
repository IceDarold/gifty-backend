from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.dialogue_manager import DialogueManager
from recommendations.models import (
    DialogueStep,
    Hypothesis,
    QuizAnswers,
    RecommendationSession,
    RecipientProfile,
    RecipientResponse,
    TopicTrack,
)


class _MemStorage:
    def __init__(self):
        self._sessions: dict[str, RecommendationSession] = {}

    async def save_session(self, session: RecommendationSession):
        self._sessions[session.session_id] = session

    async def get_session(self, session_id: str):
        return self._sessions.get(session_id)


def _quiz(*, interests=None) -> QuizAnswers:
    return QuizAnswers(
        relationship="friend",
        gifting_goal="joke",
        effort_level="low",
        session_mode="quick_fix",
        budget=1000,
        deadline_days=7,
        language="ru",
        recipient_age=25,
        recipient_gender=None,
        occasion=None,
        vibe="cozy",
        interests=interests or [],
        interests_description=None,
    )


def _session_with_track(session_id: str = "s1") -> RecommendationSession:
    recipient_uuid = str(uuid.uuid4())
    h = Hypothesis(
        id=str(uuid.uuid4()),
        title="Idea",
        description="D",
        reasoning="R",
        primary_gap="the_mirror",
        preview_products=[],
        search_queries=["q"],
    )
    track = TopicTrack(
        topic_id=str(uuid.uuid4()),
        topic_name="T",
        status="ready",
        title="title",
        preview_text="p",
        hypotheses=[h],
        question=None,
    )
    profile = RecipientProfile(
        id=recipient_uuid,
        owner_id=None,
        name=None,
        quiz_data=_quiz(interests=["x"]),
        findings=[],
        interactions=[],
        liked_hypotheses=[],
        liked_labels=[],
        ignored_hypotheses=[],
        ignored_labels=[],
        shortlist=[],
        required_effort="low",
        budget=1000,
        deadline_days=7,
        language="ru",
    )
    return RecommendationSession(
        session_id=session_id,
        recipient=RecipientResponse(id=recipient_uuid, name=None),
        full_recipient=profile,
        topics=["x"],
        language="ru",
        tracks=[track],
        liked_hypotheses=[],
        shortlisted_products=[],
        topic_hints=[],
        selected_topic_id=track.topic_id,
        selected_hypothesis_id=None,
        current_probe=None,
    )


@pytest.mark.anyio
async def test_create_track_from_data_wide_topic(monkeypatch):
    ai = AsyncMock()
    rec = AsyncMock()
    mgr = DialogueManager(ai, rec, _MemStorage(), db=None, recipient_service=None)
    session = _session_with_track()

    raw = {"is_wide": True, "question": "Q", "branches": ["a", "b"]}
    track = await mgr._create_track_from_data(session, "Topic", raw)
    assert track.status == "question"
    assert track.question.question == "Q"
    assert "a" in track.question.options


@pytest.mark.anyio
async def test_create_track_from_data_no_hypotheses_probe_success_and_failure(monkeypatch):
    ai = AsyncMock()
    ai.generate_personalized_probe = AsyncMock(return_value={"question": "Q", "options": ["1"]})
    rec = AsyncMock()
    mgr = DialogueManager(ai, rec, _MemStorage(), db=None, recipient_service=None)
    session = _session_with_track()

    track = await mgr._create_track_from_data(session, "Topic", {"hypotheses": []})
    assert track.status == "question"
    assert track.question.question == "Q"

    ai.generate_personalized_probe = AsyncMock(side_effect=RuntimeError("boom"))
    track2 = await mgr._create_track_from_data(session, "Topic", {"hypotheses": []})
    assert track2.status == "question"
    assert track2.question.question


@pytest.mark.anyio
async def test_create_track_from_data_hypotheses_preview_fetch_error_is_swallowed(monkeypatch):
    ai = AsyncMock()
    rec = AsyncMock()
    rec.find_preview_products = AsyncMock(side_effect=RuntimeError("boom"))
    mgr = DialogueManager(ai, rec, _MemStorage(), db=None, recipient_service=None)
    session = _session_with_track()

    track = await mgr._create_track_from_data(session, "Topic", {"hypotheses": [{"title": "H1", "search_queries": ["q"]}]})
    assert track.status == "ready"
    assert track.hypotheses[0].preview_products == []


@pytest.mark.anyio
async def test_create_track_for_topic_classification_error_notifies(monkeypatch):
    notifier = SimpleNamespace(notify=AsyncMock())
    monkeypatch.setattr("app.services.dialogue_manager.get_notification_service", lambda: notifier)

    ai = AsyncMock()
    ai.classify_topic = AsyncMock(side_effect=RuntimeError("boom"))
    ai.generate_hypotheses = AsyncMock(return_value=[{"title": "H", "search_queries": ["q"]}])
    rec = AsyncMock()
    rec.find_preview_products = AsyncMock(return_value=[])

    mgr = DialogueManager(ai, rec, _MemStorage(), db=None, recipient_service=None)
    session = _session_with_track()

    track = await mgr._create_track_for_topic(session, "Topic")
    assert track.status in {"ready", "question"}
    assert notifier.notify.await_count == 1


@pytest.mark.anyio
async def test_init_session_dead_end_probe_when_no_topics(monkeypatch):
    notifier = SimpleNamespace(notify=AsyncMock())
    monkeypatch.setattr("app.services.dialogue_manager.get_notification_service", lambda: notifier)

    ai = AsyncMock()
    ai.normalize_topics = AsyncMock(return_value=[])
    ai.generate_personalized_probe = AsyncMock(return_value={"question": "Q", "options": ["1"], "can_skip": True, "context_tags": ["x"]})
    ai.generate_hypotheses_bulk = AsyncMock(return_value={})
    rec = AsyncMock()

    storage = _MemStorage()
    mgr = DialogueManager(ai, rec, storage, db=None, recipient_service=None)
    session = await mgr.init_session(_quiz(interests=[]), user_id=None)
    assert session.current_probe is not None
    assert session.current_probe.question == "Q"


@pytest.mark.anyio
async def test_init_session_normalization_failure_sends_notification_and_falls_back(monkeypatch):
    notifier = SimpleNamespace(notify=AsyncMock())
    monkeypatch.setattr("app.services.dialogue_manager.get_notification_service", lambda: notifier)

    ai = AsyncMock()
    ai.normalize_topics = AsyncMock(side_effect=RuntimeError("boom"))
    ai.generate_hypotheses_bulk = AsyncMock(return_value={"x": {"hypotheses": []}})
    ai.generate_personalized_probe = AsyncMock(return_value={"question": "Q", "options": []})
    ai.classify_topic = AsyncMock(return_value={"is_wide": True, "question": "Q", "branches": []})
    rec = AsyncMock()

    storage = _MemStorage()
    mgr = DialogueManager(ai, rec, storage, db=None, recipient_service=None)
    session = await mgr.init_session(_quiz(interests=["x"]), user_id=None)
    assert session.topics == ["x"]
    assert notifier.notify.await_count == 1


@pytest.mark.anyio
async def test_init_session_bulk_generation_failure_falls_back_to_individual(monkeypatch):
    notifier = SimpleNamespace(notify=AsyncMock())
    monkeypatch.setattr("app.services.dialogue_manager.get_notification_service", lambda: notifier)

    ai = AsyncMock()
    ai.normalize_topics = AsyncMock(return_value=["t1", "t2"])
    ai.generate_hypotheses_bulk = AsyncMock(side_effect=RuntimeError("boom"))
    ai.classify_topic = AsyncMock(return_value={"is_wide": True, "question": "Q", "branches": []})
    rec = AsyncMock()

    storage = _MemStorage()
    mgr = DialogueManager(ai, rec, storage, db=None, recipient_service=None)
    session = await mgr.init_session(_quiz(interests=["t1", "t2"]), user_id=None)
    assert len(session.tracks) == 2
    assert notifier.notify.await_count == 1


@pytest.mark.anyio
async def test_interact_like_dislike_unlike_undislike_and_select_gift(monkeypatch):
    storage = _MemStorage()
    session = _session_with_track("s1")
    await storage.save_session(session)

    ai = AsyncMock()
    rec = AsyncMock()
    rec.get_deep_dive_products = AsyncMock(return_value=[{"id": "p1"}])
    recipient_service = AsyncMock()
    recipient_service.save_interaction = AsyncMock()
    recipient_service.update_hypothesis_reaction = AsyncMock()

    mgr = DialogueManager(ai, rec, storage, db=None, recipient_service=recipient_service)

    h_id = session.tracks[0].hypotheses[0].id

    out = await mgr.interact("s1", "like_hypothesis", value=h_id, metadata={})
    assert out.selected_hypothesis_id == h_id
    assert out.tracks[0].hypotheses[0].preview_products == [{"id": "p1"}]

    out2 = await mgr.interact("s1", "dislike_hypothesis", value=h_id, metadata={})
    assert h_id in out2.full_recipient.ignored_hypotheses

    out3 = await mgr.interact("s1", "undislike_hypothesis", value=h_id, metadata={})
    assert h_id not in out3.full_recipient.ignored_hypotheses

    out4 = await mgr.interact("s1", "unlike_hypothesis", value=h_id, metadata={})
    assert h_id not in out4.liked_hypotheses

    out5 = await mgr.interact("s1", "select_gift", value="gift1", metadata={})
    assert "gift1" in out5.full_recipient.shortlist


@pytest.mark.anyio
async def test_interact_session_not_found_raises():
    mgr = DialogueManager(AsyncMock(), AsyncMock(), _MemStorage(), db=None, recipient_service=None)
    with pytest.raises(ValueError):
        await mgr.interact("missing", "x", value=None, metadata={})
