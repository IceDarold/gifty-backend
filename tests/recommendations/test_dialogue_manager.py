import pytest
import uuid
from recommendations.models import RecipientProfile, QuizAnswers
from app.services.dialogue_manager import DialogueManager
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_init_session_happy_path(
    mock_anthropic_service, 
    mock_session_storage
):
    recommendation_service = AsyncMock()
    recommendation_service.find_preview_products.return_value = []
    
    # Mock normalization to return what dm expects
    mock_anthropic_service.normalize_topics.return_value = ["Coffee"]
    mock_anthropic_service.generate_hypotheses_bulk.return_value = {
        "Coffee": {
            "hypotheses": [
                {"title": "H1", "description": "D1", "reasoning": "R1", "primary_gap": "the_catalyst"}
            ]
        }
    }

    dm = DialogueManager(
        anthropic_service=mock_anthropic_service,
        recommendation_service=recommendation_service,
        session_storage=mock_session_storage,
        recipient_service=AsyncMock()
    )
    
    quiz = QuizAnswers(
        interests=["Coffee"], 
        recipient_age=30, 
        recipient_gender="male"
    )
    
    session = await dm.init_session(quiz, user_id=None)
    
    assert session is not None
    assert len(session.tracks) == 1
    assert session.tracks[0].topic_name == "Coffee"

@pytest.mark.asyncio
async def test_interact_like_hypothesis(
    mock_anthropic_service,
    mock_session_storage
):
    recommendation_service = AsyncMock()
    recommendation_service.get_deep_dive_products.return_value = []
    
    dm = DialogueManager(
        anthropic_service=mock_anthropic_service,
        recommendation_service=recommendation_service,
        session_storage=mock_session_storage,
        recipient_service=AsyncMock()
    )
    
    rec_id = str(uuid.uuid4())
    hypo_id = str(uuid.uuid4())
    track_id = str(uuid.uuid4())

    from recommendations.models import RecommendationSession, TopicTrack, Hypothesis, RecipientResponse, RecipientProfile, GiftingGap
    session = RecommendationSession(
        session_id="test_session",
        recipient=RecipientResponse(id=rec_id, name="Test"),
        full_recipient=RecipientProfile(id=rec_id, name="Test", quiz_data=QuizAnswers(interests=["X"], recipient_age=20)),
        tracks=[
            TopicTrack(
                topic_id=track_id, 
                topic_name="Coffee", 
                hypotheses=[Hypothesis(id=hypo_id, title="Espresso Machine", description="D", reasoning="R", primary_gap=GiftingGap.CATALYST)]
            )
        ]
    )
    mock_session_storage.get_session.return_value = session
    
    updated_session = await dm.interact("test_session", "like_hypothesis", hypo_id)
    
    assert hypo_id in updated_session.liked_hypotheses
    assert "Espresso Machine" in updated_session.full_recipient.liked_labels

@pytest.mark.asyncio
async def test_load_more_hypotheses_deduplication(
    mock_anthropic_service,
    mock_session_storage
):
    dm = DialogueManager(
        anthropic_service=mock_anthropic_service,
        recommendation_service=AsyncMock(),
        session_storage=mock_session_storage,
        db=AsyncMock()
    )
    
    rec_id = str(uuid.uuid4())
    hypo_id = str(uuid.uuid4())
    track_id = str(uuid.uuid4())

    from recommendations.models import RecommendationSession, TopicTrack, Hypothesis, RecipientResponse, RecipientProfile, GiftingGap
    session = RecommendationSession(
        session_id="test_session",
        recipient=RecipientResponse(id=rec_id, name="Test"),
        full_recipient=RecipientProfile(id=rec_id, name="Test", quiz_data=QuizAnswers(interests=["X"], recipient_age=20)),
        tracks=[
            TopicTrack(
                topic_id=track_id, 
                topic_name="Coffee", 
                hypotheses=[Hypothesis(id=hypo_id, title="Espresso Machine", description="D", reasoning="R", primary_gap=GiftingGap.CATALYST)]
            )
        ]
    )
    mock_session_storage.get_session.return_value = session
    
    await dm.interact("test_session", "load_more_hypotheses", track_id)
    
    kwargs = mock_anthropic_service.generate_hypotheses.call_args.kwargs
    assert "Espresso Machine" in kwargs["shown_concepts"]

@pytest.mark.asyncio
async def test_suggest_topics_action(
    mock_anthropic_service,
    mock_session_storage
):
    dm = DialogueManager(
        anthropic_service=mock_anthropic_service,
        recommendation_service=AsyncMock(),
        session_storage=mock_session_storage,
        db=AsyncMock()
    )
    
    rec_id = str(uuid.uuid4())
    from recommendations.models import RecommendationSession, RecipientResponse, RecipientProfile
    session = RecommendationSession(
        session_id="test_session",
        recipient=RecipientResponse(id=rec_id, name="Test"),
        full_recipient=RecipientProfile(id=rec_id, name="Test", quiz_data=QuizAnswers(interests=["X"], recipient_age=20)),
        tracks=[]
    )
    mock_session_storage.get_session.return_value = session
    
    updated_session = await dm.interact("test_session", "suggest_topics")
    assert len(updated_session.topic_hints) > 0
