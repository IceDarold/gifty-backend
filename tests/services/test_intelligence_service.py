
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.intelligence import IntelligenceAPIClient
from app.models import ComputeTask

@pytest.fixture
def intelligence_client():
    client = IntelligenceAPIClient()
    # Set dummy credentials to satisfy checks
    client.runpod_api_key = "test-runpod-key"
    client.runpod_endpoint_id = "test-endpoint"
    client.together_api_key = "test-together-key"
    client.intelligence_api_token = "test-api-token"
    return client

@pytest.mark.asyncio
async def test_get_embeddings_online_runpod(intelligence_client):
    with patch("app.services.intelligence.logic_config") as mock_logic:
        mock_logic.llm.embedding_provider = "runpod"
        mock_logic.model_embedding = "test-model"
        
        # Mock httpx.AsyncClient instance
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "output": {"embeddings": [[0.1, 0.2], [0.3, 0.4]]}
        }
        mock_resp.raise_for_status = MagicMock()
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            
            texts = ["hello", "world"]
            res = await intelligence_client.get_embeddings(texts, priority="high")
            
            assert res == [[0.1, 0.2], [0.3, 0.4]]
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            assert "Authorization" in kwargs["headers"]
            assert f"Bearer {intelligence_client.runpod_api_key}" == kwargs["headers"]["Authorization"]

@pytest.mark.asyncio
async def test_get_embeddings_online_together(intelligence_client):
    with patch("app.services.intelligence.logic_config") as mock_logic:
        mock_logic.llm.embedding_provider = "together"
        mock_logic.model_embedding = "test-model"
        
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [{"embedding": [0.5, 0.6]}]
        }
        mock_resp.raise_for_status = MagicMock()
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            
            texts = ["test"]
            res = await intelligence_client.get_embeddings(texts, priority="high")
            
            assert res == [[0.5, 0.6]]

@pytest.mark.asyncio
async def test_get_embeddings_offline(intelligence_client):
    mock_db = MagicMock(spec=AsyncSession) # Use MagicMock for sync add()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    
    texts = ["offline text"]
    with patch("app.services.intelligence.logic_config") as mock_logic:
        mock_logic.model_embedding = "test-model"
        
        res = await intelligence_client.get_embeddings(texts, priority="low", db=mock_db)
        
        assert res is None
        mock_db.add.assert_called_once()
        task = mock_db.add.call_args[0][0]
        assert task.task_type == "embedding"
        mock_db.commit.assert_called_once()

@pytest.mark.asyncio
async def test_rerank_online(intelligence_client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"scores": [0.9, 0.1]}
    mock_resp.raise_for_status = MagicMock()
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        
        query = "best gift"
        docs = ["iphone", "socks"]
        res = await intelligence_client.rerank(query, docs, priority="high")
        
        assert res == [0.9, 0.1]

@pytest.mark.asyncio
async def test_rerank_offline(intelligence_client):
    mock_db = MagicMock(spec=AsyncSession)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    
    query = "q"
    docs = ["d1"]
    res = await intelligence_client.rerank(query, docs, priority="low", db=mock_db)
    
    assert res is None
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_fallback_logic(intelligence_client):
    # Test that if Together fails, it falls back to Intelligence API
    with patch("app.services.intelligence.logic_config") as mock_logic:
        mock_logic.llm.embedding_provider = "together"
        intelligence_client.together_api_key = "key"
        
        # First call fails, second call (fallback) succeeds
        mock_responses = [
            AsyncMock(side_effect=Exception("Together Error")), # Together call
            AsyncMock(return_value=MagicMock(status_code=200, json=MagicMock(return_value={"data": [{"embedding": [0.0]}]}))) # API call
        ]
        
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.side_effect = Exception("Together error")
            
            # Wait, IntelligenceAPIClient uses multiple calls.
            # IntelligenceAPIClient._get_embeddings_online calls _call_together_embeddings
            # which has a try-except and then calls _call_intelligence_api_embeddings
            
            # So _call_together_embeddings will catch the exception and return
            # But wait, looking at code:
            # try: return await self._call_together_embeddings(texts)
            # except Exception as e: logger.warning(...); pass
            # return await self._call_intelligence_api_embeddings(texts)
            
            with patch.object(intelligence_client, "_call_together_embeddings", side_effect=Exception("Error")):
                with patch.object(intelligence_client, "_call_intelligence_api_embeddings", new_callable=AsyncMock) as mock_api:
                    mock_api.return_value = [[1.0]]
                    res = await intelligence_client.get_embeddings(["t"], priority="high")
                    assert res == [[1.0]]
                    mock_api.assert_called_once()
