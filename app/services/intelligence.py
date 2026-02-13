import httpx
import logging
from typing import List, Optional
from app.config import get_settings
from app.core.logic_config import logic_config

logger = logging.getLogger(__name__)

class IntelligenceAPIClient:
    """
    Client for Gifty Intelligence API.
    Handles embeddings, reranking, and other ML tasks.
    """
    def __init__(self):
        settings = get_settings()
        self.base_url = settings.intelligence_api_base
        self.token = settings.intelligence_api_token
        self.timeout = 10.0

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Request embeddings for a list of texts.
        """
        if not self.token:
            logger.warning("IntelligenceAPI token missing, using dummy embeddings.")
            return [[0.0] * 1024 for _ in texts]

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/v1/embeddings",
                    json={"input": texts, "model": logic_config.model_embedding},
                    headers={"Authorization": f"Bearer {self.token}"}
                )
                response.raise_for_status()
                data = response.json()
                # Expecting format similar to OpenAI: {"data": [{"embedding": [...]}, ...]}
                return [item["embedding"] for item in data.get("data", [])]
        except Exception as e:
            logger.error(f"IntelligenceAPI embeddings call failed: {e}")
            # Fallback to dummy
            return [[0.0] * 1024 for _ in texts]

    async def rerank(self, query: str, documents: List[str]) -> List[float]:
        """
        Request reranking scores for documents relative to a query.
        """
        if not self.token:
            return [0.0] * len(documents)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/v1/rerank",
                    json={"query": query, "documents": documents},
                    headers={"Authorization": f"Bearer {self.token}"}
                )
                response.raise_for_status()
                return response.json().get("scores", [0.0] * len(documents))
        except Exception as e:
            logger.error(f"IntelligenceAPI rerank call failed: {e}")
            return [0.0] * len(documents)

_client: Optional[IntelligenceAPIClient] = None

def get_intelligence_client() -> IntelligenceAPIClient:
    global _client
    if _client is None:
        _client = IntelligenceAPIClient()
    return _client
