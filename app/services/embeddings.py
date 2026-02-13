import logging
import asyncio
from typing import List, Optional
from app.services.intelligence import get_intelligence_client

logger = logging.getLogger(__name__)

class EmbeddingService:
    def __init__(self, model_name: str = "BAAI/bge-m3"):
        self.model_name = model_name
        self.intelligence_client = get_intelligence_client()

    def load_model(self) -> None:
        """Embeddings are now handled by IntelligenceAPI."""
        logger.info(f"EmbeddingService using IntelligenceAPI for {self.model_name}")

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Synchronous wrapper for backward compatibility or scripts.
        WARNING: This uses asyncio.run() or existing loop, which can be problematic in async code.
        Better use embed_batch_async.
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        if loop.is_running():
            # This is risky but often needed when patching sync codebases
            # Ideally we refactor caller to be async
            return asyncio.run_coroutine_threadsafe(self.embed_batch_async(texts), loop).result()
        else:
            return loop.run_until_complete(self.embed_batch_async(texts))

    async def embed_batch_async(self, texts: List[str]) -> List[List[float]]:
        """
        Asynchronously get embeddings from IntelligenceAPI.
        """
        if not texts:
            return []
        
        return await self.intelligence_client.get_embeddings(texts)

def get_embedding_service() -> EmbeddingService:
    from app.config import get_settings
    settings = get_settings()
    return EmbeddingService(model_name=settings.embedding_model)
