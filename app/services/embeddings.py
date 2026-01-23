from __future__ import annotations

import logging
from typing import Optional

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self, model_name: str = "BAAI/bge-m3", device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self._model: Optional[SentenceTransformer] = None

    def load_model(self) -> None:
        if self._model is None:
            logger.info(f"Loading embedding model {self.model_name} on {self.device}...")
            self._model = SentenceTransformer(self.model_name, device=self.device)
            logger.info("Model loaded.")

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        
        self.load_model()
        # BAAI/bge-m3 usually outputs normalized embeddings by default, 
        # but explicit normalize_embeddings=True ensures cosine similarity works correctly.
        embeddings = self._model.encode(
            texts, 
            batch_size=len(texts), 
            normalize_embeddings=True,
            show_progress_bar=False
        )
        
        # Convert numpy array to list of lists
        return embeddings.tolist()
