import pytest
from app.services.embeddings import get_embedding_service
from app.services.session_storage import get_session_storage
from app.services.recommendation import RecommendationService
from app.services.dialogue_manager import DialogueManager
from app.services.ai_reasoning_service import AIReasoningService
from app.db import get_db

@pytest.mark.asyncio
async def test_factories_sanity():
    """
    Sanity test to ensure all major service factories can be initialized
    without common errors like AttributeError (missing config keys).
    """
    # 1. Test Embedding Service Factory
    # This would have caught the AttributeError: 'Settings' has no attribute 'embedding_model'
    try:
        emb = get_embedding_service()
        assert emb is not None
    except Exception as e:
        pytest.fail(f"Embedding service factory failed: {e}")

    # 2. Test Session Storage Factory
    try:
        storage = get_session_storage()
        assert storage is not None
    except Exception as e:
        pytest.fail(f"Session storage factory failed: {e}")

    # 3. Test AI Reasoning Service
    try:
        ai = AIReasoningService()
        assert ai is not None
    except Exception as e:
        pytest.fail(f"AI Reasoning service failed: {e}")
