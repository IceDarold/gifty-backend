import sys
import pytest
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from recommendations.models import RecommendationSession, TopicTrack, DialogueStep, QuizAnswers, RecipientProfile, RecipientResponse
from app.models import Product
from app.services.dialogue_manager import DialogueManager

@pytest.mark.asyncio
async def test_wide_topic_branching(mock_anthropic_service, mock_session_storage):
    """Verify that a topic marked as 'wide' by AI triggers a branching question."""
    dm = DialogueManager(
        anthropic_service=mock_anthropic_service,
        recommendation_service=AsyncMock(),
        session_storage=mock_session_storage,
        recipient_service=AsyncMock()
    )
    
    mock_anthropic_service.normalize_topics.return_value = ["Politics"]
    mock_anthropic_service.generate_hypotheses_bulk.return_value = {
        "Politics": {
            "is_wide": True,
            "question": "What kind of politics?",
            "branches": ["Domestic", "International"]
        }
    }
    
    quiz = QuizAnswers(interests=["Politics"], recipient_age=40)
    session = await dm.init_session(quiz)
    
    track = session.tracks[0]
    assert track.status == "question"
    assert track.question.question == "What kind of politics?"
    assert "Domestic" in track.question.options

@pytest.mark.asyncio
async def test_personalized_probe_fallback(mock_anthropic_service, mock_session_storage):
    """Verify that if AI returns no hypotheses, a personalized probe is generated."""
    dm = DialogueManager(
        anthropic_service=mock_anthropic_service,
        recommendation_service=AsyncMock(),
        session_storage=mock_session_storage,
        recipient_service=AsyncMock()
    )
    
    mock_anthropic_service.normalize_topics.return_value = ["Obscure Hobby"]
    # AI returns successfully but with empty hypotheses
    mock_anthropic_service.generate_hypotheses_bulk.return_value = {
        "Obscure Hobby": {"hypotheses": []}
    }
    mock_anthropic_service.generate_personalized_probe.return_value = {
        "question": "Tell me more about this hobby?",
        "options": ["It's niche", "It's expensive"]
    }
    
    quiz = QuizAnswers(interests=["Obscure Hobby"], recipient_age=25)
    session = await dm.init_session(quiz)
    
    track = session.tracks[0]
    assert track.status == "question"
    assert track.question.question == "Tell me more about this hobby?"

@pytest.mark.asyncio
async def test_session_history_clipping():
    """Verify that session history is limited to the last 30 interactions."""
    session_storage = AsyncMock()
    dm = DialogueManager(
        anthropic_service=AsyncMock(),
        recommendation_service=AsyncMock(),
        session_storage=session_storage,
        recipient_service=AsyncMock()
    )
    
    # Interactions are in full_recipient.interactions
    session = RecommendationSession(
        session_id="long_session",
        recipient=RecipientResponse(id="r1", name="N"),
        full_recipient=RecipientProfile(
            id="r1", 
            name="N", 
            quiz_data=QuizAnswers(recipient_age=20),
            interactions=[{"type": "view", "timestamp": 0, "target_id": "x", "target_type": "y"}] * 35
        )
    )
    session_storage.get_session.return_value = session
    
    # Trigger any action that saves session
    await dm.interact("long_session", "select_track", value="any_id")
    
    saved_session = session_storage.save_session.call_args[0][0]
    assert len(saved_session.full_recipient.interactions) == 30
