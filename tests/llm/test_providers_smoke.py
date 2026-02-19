import pytest
import logging
from app.services.llm.factory import LLMFactory
from app.services.llm.interface import Message
from app.services.intelligence import get_intelligence_client
from app.core.logic_config import logic_config

logger = logging.getLogger(__name__)

@pytest.mark.ai_test
@pytest.mark.asyncio
async def test_llm_provider_smoke():
    """
    Smoke test for the currently configured LLM provider.
    Checks if we can get a simple reply.
    """
    provider = logic_config.llm.default_provider
    logger.info(f"Testing LLM provider: {provider}")
    
    # Skip if key is missing or is just a mock placeholder (common in CI)
    from app.config import get_settings
    settings = get_settings()
    if not settings.anthropic_api_key or settings.anthropic_api_key.startswith("sk-ant-mock"):
        pytest.skip("Anthropic API key is default/mock, skipping live smoke test")

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
        error_str = str(e)
        if any(msg in error_str for msg in ["Authentication", "401", "credit balance"]):
             pytest.skip(f"Skipping due to auth or billing issue: {e}")
        pytest.fail(f"LLM Provider {provider} failed: {e}")

@pytest.mark.ai_test
@pytest.mark.asyncio
async def test_embedding_provider_smoke():
    """
    Smoke test for the currently configured Embedding provider.
    """
    provider = logic_config.llm.embedding_provider
    logger.info(f"Testing Embedding provider: {provider}")
    
    # Skip if Intelligence API key is default/mock
    from app.config import get_settings
    settings = get_settings()
    if not settings.intelligence_api_token or "token" in settings.intelligence_api_token:
        pytest.skip("Intelligence API token not set, skipping embedding smoke test")

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
