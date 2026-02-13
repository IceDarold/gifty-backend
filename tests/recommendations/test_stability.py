import sys
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))
from unittest.mock import AsyncMock, patch
from app.utils.errors import install_exception_handlers
from fastapi import FastAPI, Request
from app.models import Product
from starlette.testclient import TestClient

@pytest.fixture
def test_app():
    app = FastAPI()
    
    @app.get("/error")
    async def trigger_error():
        raise ValueError("Boom!")
    
    install_exception_handlers(app)
    return app

@pytest.mark.asyncio
async def test_global_exception_notification(test_app, mock_notification_service):
    # The handler in app/utils/errors.py uses get_notification_service via internal import
    with patch("app.services.notifications.get_notification_service", return_value=mock_notification_service):
        client = TestClient(test_app, raise_server_exceptions=False)
        response = client.get("/error")
        
        assert response.status_code == 500
        mock_notification_service.notify.assert_called_once()

@pytest.mark.asyncio
async def test_proactive_ai_notification_in_dm(
    mock_anthropic_service, 
    mock_notification_service,
    mock_session_storage
):
    from app.services.dialogue_manager import DialogueManager
    mock_anthropic_service.normalize_topics.side_effect = Exception("AI Offline")
    
    dm = DialogueManager(
        anthropic_service=mock_anthropic_service,
        recommendation_service=AsyncMock(),
        session_storage=mock_session_storage,
        db=AsyncMock()
    )
    
    with patch("app.services.dialogue_manager.get_notification_service", return_value=mock_notification_service):
        from recommendations.models import QuizAnswers
        quiz = QuizAnswers(interests=["X"], recipient_age=20)
        await dm.init_session(quiz)
        
        mock_notification_service.notify.assert_called_once()

@pytest.mark.asyncio
async def test_find_preview_products_partial_failure(mock_intelligence_client):
    """Verify that if one search task fails, others still succeed."""
    from app.services.recommendation import RecommendationService
    catalog_repo = AsyncMock()
    embedding_service = AsyncMock()
    
    # Mock three queries
    p1 = Product(gift_id="p1", title="Success 1", product_url="https://a.com")
    p2 = Product(gift_id="p2", title="Success 2", product_url="https://b.com")
    
    # Side effect: query 1 fails, query 2 succeeds, query 3 succeeds
    catalog_repo.search_similar_products.side_effect = [
        Exception("Search fail"), # Query 1
        [p1],                     # Query 2 
        [p2]                      # Query 3
    ]
    embedding_service.embed_batch_async.return_value = [[0.1] * 1024]
    
    service = RecommendationService(session=AsyncMock(), embedding_service=embedding_service)
    service.repo = catalog_repo
    service.intelligence_client = mock_intelligence_client
    
    results = await service.find_preview_products(
        search_queries=["fail", "success1", "success2"],
        hypothesis_title="Test"
    )
    
    # Should have products from both successful queries
    assert len(results) >= 2
    assert any(g.id == "p1" for g in results)
    assert any(g.id == "p2" for g in results)

@pytest.mark.asyncio
async def test_rerank_failure_notification(mock_notification_service):
    """Verify notification is sent if intelligence reranking fails."""
    from app.services.recommendation import RecommendationService
    intelligence_client = AsyncMock()
    intelligence_client.rerank.side_effect = Exception("Intelligence API Down")
    
    catalog_repo = AsyncMock()
    p1 = Product(gift_id="p1", title="A", product_url="https://a.com")
    catalog_repo.search_similar_products.return_value = [p1]
    
    service = RecommendationService(session=AsyncMock(), embedding_service=AsyncMock())
    service.repo = catalog_repo
    service.intelligence_client = intelligence_client
    
    with patch("app.services.recommendation.get_notification_service", return_value=mock_notification_service):
        await service.find_preview_products(
            search_queries=["q1"],
            hypothesis_title="Fail Test"
        )
        
        mock_notification_service.notify.assert_called_once()
        args = mock_notification_service.notify.call_args
        assert args.kwargs["topic"] == "intelligence_error"
