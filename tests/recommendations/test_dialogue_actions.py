import sys
import pytest
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from recommendations.models import RecommendationSession, TopicTrack, Hypothesis, RecipientResponse, RecipientProfile, QuizAnswers
from app.services.dialogue_manager import DialogueManager

@pytest.fixture
def mock_session():
    rec_id = str(uuid.uuid4())
    track_id = str(uuid.uuid4())
    return RecommendationSession(
        session_id="test_session",
        recipient=RecipientResponse(id=rec_id, name="Test"),
        full_recipient=RecipientProfile(id=rec_id, name="Test", quiz_data=QuizAnswers(interests=["X"], recipient_age=20)),
        tracks=[
            TopicTrack(
                topic_id=track_id, 
                topic_name="Coffee", 
                status="question",
                hypotheses=[]
            )
        ]
    )

@pytest.mark.asyncio
async def test_action_answer_probe_refines(mock_anthropic_service, mock_session_storage, mock_session):
    """Verify answering a probe refines the track."""
    dm = DialogueManager(
        anthropic_service=mock_anthropic_service,
        recommendation_service=AsyncMock(),
        session_storage=mock_session_storage,
        recipient_service=AsyncMock()
    )
    mock_session_storage.get_session.return_value = mock_session
    track_id = mock_session.tracks[0].topic_id
    
    # Mock individual track creation (fallback/refinement logic)
    refined_track = TopicTrack(topic_id="new_id", topic_name="Special Coffee")
    with patch.object(dm, "_create_track_for_topic", return_value=refined_track):
        updated = await dm.interact("test_session", "answer_probe", value="Espresso", metadata={"topic_id": track_id})
        
        assert updated.selected_topic_id == "new_id"
        assert updated.tracks[0].topic_name == "Special Coffee"

@pytest.mark.asyncio
async def test_action_select_track(mock_session_storage, mock_session):
    """Verify track selection switching."""
    dm = DialogueManager(
        anthropic_service=AsyncMock(),
        recommendation_service=AsyncMock(),
        session_storage=mock_session_storage,
        recipient_service=AsyncMock()
    )
    new_track_id = str(uuid.uuid4())
    mock_session.tracks.append(TopicTrack(topic_id=new_track_id, topic_name="Tea"))
    mock_session_storage.get_session.return_value = mock_session
    
    updated = await dm.interact("test_session", "select_track", value=new_track_id)
    assert updated.selected_topic_id == new_track_id

@pytest.mark.asyncio
async def test_persistence_failure_resilience(mock_anthropic_service, mock_session_storage, mock_session):
    """Verify that interaction succeeds even if DB persistence fails."""
    recipient_service = AsyncMock()
    recipient_service.save_hypotheses.side_effect = Exception("DB Down")
    
    dm = DialogueManager(
        anthropic_service=mock_anthropic_service,
        recommendation_service=AsyncMock(),
        session_storage=mock_session_storage,
        recipient_service=recipient_service
    )
    mock_session_storage.get_session.return_value = mock_session
    track_id = mock_session.tracks[0].topic_id
    
    mock_anthropic_service.generate_hypotheses.return_value = [{"title": "H1"}]
    
    # This should NOT raise Exception
    updated = await dm.interact("test_session", "load_more_hypotheses", value=track_id)
    assert len(updated.tracks[0].hypotheses) > 0
