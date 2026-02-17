import pytest
import pytest_asyncio
import uuid
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app.main import app
from app.db import get_db
from app.services.session_storage import get_session_storage
from app.services.dialogue_manager import DialogueManager
from routes.recommendations import get_dialogue_manager

@pytest_asyncio.fixture
async def e2e_client(sqlite_db_session, in_memory_session_storage):
    # Overrides for testing
    async def override_get_db():
        yield sqlite_db_session

    def override_get_session_storage():
        return in_memory_session_storage

    # Mock embedding service
    mock_emb = AsyncMock()
    mock_emb.embed_batch_async.return_value = [[0.1] * 1024]
    
    # Mock Recommendation Service
    mock_rec = AsyncMock()
    from app.schemas_v2 import GiftDTO
    mock_gift = GiftDTO(
        id="prod-123",
        title="Test Product",
        price=4500.0,
        product_url="https://example.com/p/123",
        is_active=True
    )
    mock_rec.get_deep_dive_products.return_value = [mock_gift]
    mock_rec.find_preview_products.return_value = [mock_gift]

    async def override_get_dialogue_manager():
        # We need the real DialogueManager logic for session state, 
        # but with our mocked components
        from app.services.anthropic_service import AnthropicService
        return DialogueManager(AnthropicService(), mock_rec, in_memory_session_storage, db=sqlite_db_session)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_session_storage] = override_get_session_storage
    app.dependency_overrides[get_dialogue_manager] = override_get_dialogue_manager
    app.state.embedding_service = mock_emb

    with TestClient(app) as client:
        yield client
    
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_full_discovery_flow_e2e(e2e_client, sqlite_db_session, in_memory_session_storage):
    """
    Test the full discovery flow path:
    1. /init -> Start session (and save to DB)
    2. /interact -> Like a hypothesis
    3. /hypothesis/{id}/products -> Get recommendations
    4. /hypothesis/{id}/react -> Final reaction (shortlist)
    """
    
    user_id = str(uuid.uuid4())
    
    # --- STEP 1: INIT ---
    quiz_data = {
        "interests": ["Coffee", "Gadgets"],
        "recipient_age": 30,
        "recipient_gender": "male",
        "budget": 5000,
        "deadline_days": 7,
        "effort_level": "medium",
        "language": "ru",
        "relationship": "friend"
    }
    
    mock_hypo_id = str(uuid.uuid4())
    mock_hypo_list = [
        {
            "id": mock_hypo_id,
            "title": "AeroPress Kit",
            "description": "Brew anywhere",
            "reasoning": "He likes coffee",
            "primary_gap": "the_optimizer",
            "search_queries": ["aeropress"],
            "preview_products": []
        }
    ]
    mock_hypos_bulk = {
        "Coffee": {
            "hypotheses": mock_hypo_list
        },
        "Gadgets": {
            "hypotheses": [
                {
                    "id": str(uuid.uuid4()),
                    "title": "Smart Light",
                    "description": "RGB goodness",
                    "reasoning": "He likes tech",
                    "primary_gap": "the_catalyst",
                    "search_queries": ["smart bulbs"],
                    "preview_products": []
                }
            ]
        }
    }

    mock_notifier = AsyncMock()
    
    with patch("app.services.anthropic_service.AnthropicService.normalize_topics", AsyncMock(return_value=["Coffee", "Gadgets"])), \
         patch("app.services.anthropic_service.AnthropicService.generate_hypotheses_bulk", AsyncMock(return_value=mock_hypos_bulk)), \
         patch("app.services.anthropic_service.AnthropicService.generate_hypotheses", AsyncMock(return_value=mock_hypo_list)), \
         patch("app.services.dialogue_manager.get_notification_service", return_value=mock_notifier), \
         patch("routes.recommendations.get_session_storage", return_value=in_memory_session_storage):
        
        # Pass user_id as query param to ensure DB persistence
        response = e2e_client.post(f"/api/v1/recommendations/init?user_id={user_id}", json=quiz_data)
        assert response.status_code == 200, f"Init failed: {response.text}"
        session = response.json()
        session_id = session["session_id"]
        
        # Find hypothesis ID from tracks
        hypo_id = None
        for track in session["tracks"]:
            for h in track["hypotheses"]:
                if h["title"] == "AeroPress Kit":
                    hypo_id = h["id"]
                    break
        assert hypo_id is not None

        # --- STEP 2: INTERACT (Like) ---
        interaction_data = {
            "session_id": session_id,
            "action": "like_hypothesis",
            "value": hypo_id
        }
        
        response = e2e_client.post("/api/v1/recommendations/interact", json=interaction_data)
        assert response.status_code == 200, f"Interact failed: {response.text}"
        updated_session = response.json()
        assert hypo_id in updated_session["liked_hypotheses"]

        # --- STEP 3: GET PRODUCTS ---
        response = e2e_client.get(f"/api/v1/recommendations/hypothesis/{hypo_id}/products")
        assert response.status_code == 200, f"Products failed: {response.text}"
        products = response.json()
        assert len(products) > 0

        # --- STEP 4: FINAL REACTION ---
        response = e2e_client.post(f"/api/v1/recommendations/hypothesis/{hypo_id}/react?reaction=shortlist")
        assert response.status_code == 200, f"React failed: {response.text}"
        assert response.json()["reaction"] == "shortlist"

    # --- DB VERIFICATION ---
    from app.models import Recipient, Interaction, Hypothesis as DbHypothesis
    from sqlalchemy import select
    
    # 1. Check Recipient
    res = await sqlite_db_session.execute(select(Recipient).where(Recipient.user_id == uuid.UUID(user_id)))
    recipients = res.scalars().all()
    assert len(recipients) == 1, "Recipient not saved to DB"
    recipient_id = recipients[0].id
    
    # 2. Check Interactions (init interaction + like interaction)
    # Note: init_session doesn't explicitly save an interaction unless we add it, 
    # but interact() definitely does.
    res = await sqlite_db_session.execute(select(Interaction).where(Interaction.recipient_id == recipient_id))
    interactions = res.scalars().all()
    # Should have at least the 'like_hypothesis' interaction
    assert any(i.action_type == "like_hypothesis" for i in interactions), "Like interaction not saved"
    
    # 3. Check Hypothesis Persistence
    res = await sqlite_db_session.execute(select(DbHypothesis).where(DbHypothesis.id == uuid.UUID(hypo_id)))
    db_hypo = res.scalar_one_or_none()
    assert db_hypo is not None, "Hypothesis not saved to DB"
    assert db_hypo.user_reaction == "shortlist", f"Reaction not updated in DB: {db_hypo.user_reaction}"
