import httpx
import logging
import uuid
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.logic_config import logic_config
from app.models import ComputeTask
from app.db import get_db

logger = logging.getLogger(__name__)

class IntelligenceAPIClient:
    """
    Hybrid Intelligence Client supporting both online (RunPod/API) and offline (DB queue) execution.
    
    - Online (priority='high'): Immediate execution via RunPod or Intelligence API
    - Offline (priority='low'): Task queued in database for external workers
    """
    def __init__(self):
        settings = get_settings()
        self.intelligence_api_base = settings.intelligence_api_base
        self.intelligence_api_token = settings.intelligence_api_token
        self.runpod_api_key = settings.runpod_api_key
        self.runpod_endpoint_id = settings.runpod_endpoint_id
        self.timeout = 10.0

    async def get_embeddings(
        self, 
        texts: List[str], 
        priority: str = "high",
        db: Optional[AsyncSession] = None
    ) -> Optional[List[List[float]]]:
        """
        Get embeddings for texts.
        
        Args:
            texts: List of texts to embed
            priority: 'high' for online execution, 'low' for offline queue
            db: Database session (required if priority='low')
            
        Returns:
            List of embedding vectors if priority='high', None if priority='low' (task queued)
        """
        if priority == "low":
            if db is None:
                raise ValueError("Database session required for offline task scheduling")
            await self._schedule_task(
                db=db,
                task_type="embedding",
                payload={"texts": texts, "model": logic_config.model_embedding}
            )
            return None
        
        # Online execution (RunPod or Intelligence API)
        return await self._get_embeddings_online(texts)

    async def _get_embeddings_online(self, texts: List[str]) -> List[List[float]]:
        """Execute embeddings via RunPod or Intelligence API."""
        # Try RunPod first if configured
        if self.runpod_api_key and self.runpod_endpoint_id:
            try:
                return await self._call_runpod_embeddings(texts)
            except Exception as e:
                logger.warning(f"RunPod embeddings failed, falling back to Intelligence API: {e}")
        
        # Fallback to Intelligence API
        return await self._call_intelligence_api_embeddings(texts)

    async def _call_runpod_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Call RunPod serverless endpoint for embeddings."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"https://api.runpod.ai/v2/{self.runpod_endpoint_id}/runsync",
                json={
                    "input": {
                        "texts": texts,
                        "model": logic_config.model_embedding
                    }
                },
                headers={"Authorization": f"Bearer {self.runpod_api_key}"}
            )
            response.raise_for_status()
            data = response.json()
            return data["output"]["embeddings"]

    async def _call_intelligence_api_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Call Intelligence API for embeddings (existing implementation)."""
        if not self.intelligence_api_token:
            logger.warning("IntelligenceAPI token missing, using dummy embeddings.")
            return [[0.0] * 1024 for _ in texts]

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.intelligence_api_base}/v1/embeddings",
                    json={"input": texts, "model": logic_config.model_embedding},
                    headers={"Authorization": f"Bearer {self.intelligence_api_token}"}
                )
                response.raise_for_status()
                data = response.json()
                return [item["embedding"] for item in data.get("data", [])]
        except Exception as e:
            logger.error(f"IntelligenceAPI embeddings call failed: {e}")
            return [[0.0] * 1024 for _ in texts]

    async def rerank(
        self, 
        query: str, 
        documents: List[str],
        priority: str = "high",
        db: Optional[AsyncSession] = None
    ) -> Optional[List[float]]:
        """
        Rerank documents relative to a query.
        
        Args:
            query: Query text
            documents: List of documents to rerank
            priority: 'high' for online execution, 'low' for offline queue
            db: Database session (required if priority='low')
            
        Returns:
            List of relevance scores if priority='high', None if priority='low' (task queued)
        """
        if priority == "low":
            if db is None:
                raise ValueError("Database session required for offline task scheduling")
            await self._schedule_task(
                db=db,
                task_type="rerank",
                payload={"query": query, "documents": documents}
            )
            return None
        
        # Online execution
        return await self._rerank_online(query, documents)

    async def _rerank_online(self, query: str, documents: List[str]) -> List[float]:
        """Execute reranking via Intelligence API."""
        if not self.intelligence_api_token:
            return [0.0] * len(documents)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.intelligence_api_base}/v1/rerank",
                    json={"query": query, "documents": documents},
                    headers={"Authorization": f"Bearer {self.intelligence_api_token}"}
                )
                response.raise_for_status()
                return response.json().get("scores", [0.0] * len(documents))
        except Exception as e:
            logger.error(f"IntelligenceAPI rerank call failed: {e}")
            return [0.0] * len(documents)

    async def _schedule_task(self, db: AsyncSession, task_type: str, payload: dict) -> None:
        """Schedule a task in the database queue for offline processing."""
        task = ComputeTask(
            id=uuid.uuid4(),
            task_type=task_type,
            priority="low",
            status="pending",
            payload=payload
        )
        db.add(task)
        await db.commit()
        logger.info(f"Scheduled {task_type} task {task.id} for offline processing")


_client: Optional[IntelligenceAPIClient] = None

def get_intelligence_client() -> IntelligenceAPIClient:
    global _client
    if _client is None:
        _client = IntelligenceAPIClient()
    return _client
