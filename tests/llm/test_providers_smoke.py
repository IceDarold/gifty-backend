import pytest
import logging
from app.services.llm.factory import LLMFactory
from app.services.llm.interface import Message
from app.services.intelligence import get_intelligence_client
from app.core.logic_config import logic_config

logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_llm_provider_smoke():
    """
    Smoke test for the currently configured LLM provider.
    Checks if we can get a simple reply.
    """
    provider = logic_config.llm.default_provider
    logger.info(f"Testing LLM provider: {provider}")
    
    try:
        client = LLMFactory.get_client()
        messages = [Message(role="user", content="Say 'Integration OK' in one word.")]
        
        response = await client.generate_text(
            messages=messages,
            model=logic_config.llm.model_fast,
            max_tokens=10
        )
        
        assert response.content is not None
        assert len(response.content) > 0
        logger.info(f"LLM Response: {response.content.strip()}")
        
    except Exception as e:
        pytest.fail(f"LLM Provider {provider} failed: {e}")

@pytest.mark.asyncio
async def test_embedding_provider_smoke():
    """
    Smoke test for the currently configured Embedding provider.
    """
    provider = logic_config.llm.embedding_provider
    logger.info(f"Testing Embedding provider: {provider}")
    
    try:
        client = get_intelligence_client()
        texts = ["Hello world", "Gifty integration test"]
        
        # Test Online flow
        embeddings = await client.get_embeddings(texts, priority="high")
        
        assert embeddings is not None
        assert len(embeddings) == len(texts)
        assert len(embeddings[0]) > 0
        logger.info(f"Embeddings received: {len(embeddings)} vectors, dim={len(embeddings[0])}")
        
    except Exception as e:
        pytest.fail(f"Embedding Provider {provider} failed: {e}")
