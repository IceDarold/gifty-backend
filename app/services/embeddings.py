import logging
from typing import Optional

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self, model_name: str = "BAAI/bge-m3", device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self._model = None  # No local model

    def load_model(self) -> None:
        """Placeholder for model loading. We now use an external service."""
        logger.info(f"EmbeddingService initialized in STUB mode for {self.model_name}")

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Placeholder for external embedding API.
        Currently returns dummy vectors of dimension 1024.
        """
        if not texts:
            return []
        
        logger.warning("EmbeddingService: Returning DUMMY vectors. Implement external API call here.")
        
        # Return zeros as a temporary stub (dim 1024 to match our schema)
        dummy_vector = [0.0] * 1024
        return [dummy_vector for _ in texts]
