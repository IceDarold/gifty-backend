import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.recommendation import RecommendationService
from app.models import Product

@pytest.mark.asyncio
async def test_find_preview_products_logic(mock_intelligence_client):
    catalog_repo = AsyncMock()
    # Mock search results for two queries
    p1 = Product(gift_id="p1", title="Coffee 1", price=1000, product_url="http://p1")
    p2 = Product(gift_id="p2", title="Coffee 2", price=1100, product_url="http://p2")
    
    catalog_repo.search_similar_products.side_effect = [[p1], [p2]]
    
    service = RecommendationService(
        session=AsyncMock(),
        embedding_service=AsyncMock()
    )
    service.repo = catalog_repo
    service.intelligence_client = mock_intelligence_client
    
    results = await service.find_preview_products(
        search_queries=["q1", "q2"],
        hypothesis_title="Test Hypo",
        max_price=1000
    )
    
    assert len(results) == 2

@pytest.mark.asyncio
async def test_find_preview_products_deduplication(mock_intelligence_client):
    catalog_repo = AsyncMock()
    p1 = Product(gift_id="p1", title="Unique Coffee", price=1000, product_url="http://p1")
    catalog_repo.search_similar_products.return_value = [p1]
    
    service = RecommendationService(
        session=AsyncMock(),
        embedding_service=AsyncMock()
    )
    service.repo = catalog_repo
    service.intelligence_client = mock_intelligence_client
    
    results = await service.find_preview_products(
        search_queries=["q1", "q2"],
        hypothesis_title="Dedupe Test"
    )
    
    assert len(results) == 1

@pytest.mark.asyncio
async def test_get_deep_dive_products_rerank_fallback():
    catalog_repo = AsyncMock()
    intelligence_client = AsyncMock()
    intelligence_client.rerank.side_effect = Exception("Rerank error")
    
    p1 = Product(gift_id="p1", title="A", price=500, product_url="http://p1")
    p2 = Product(gift_id="p2", title="B", price=600, product_url="http://p2")
    catalog_repo.search_similar_products.return_value = [p1, p2]
    
    service = RecommendationService(
        session=AsyncMock(),
        embedding_service=AsyncMock()
    )
    service.repo = catalog_repo
    service.intelligence_client = intelligence_client
    
    results = await service.get_deep_dive_products(
        search_queries=["q1"],
        hypothesis_title="Title",
        hypothesis_description="Desc"
    )
    
    assert len(results) == 2
