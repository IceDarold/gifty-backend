
from __future__ import annotations

import logging
from typing import Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas_v2 import RecommendationRequest, RecommendationResponse, GiftDTO
from app.repositories.catalog import PostgresCatalogRepository

from app.services.embeddings import EmbeddingService

logger = logging.getLogger(__name__)

class RecommendationService:
    def __init__(self, session: AsyncSession, embedding_service: EmbeddingService):
        self.session = session
        self.repo = PostgresCatalogRepository(session)
        self.embedding_service = embedding_service

    async def generate_recommendations(
        self, 
        request: RecommendationRequest,
        engine_version: str = "vector_v1"
    ) -> RecommendationResponse:
        """
        Main orchestration method for recommendation generation.
        Implements Stages A, B, C, D from the roadmap.
        """
        logger.info(f"Generating recommendations for request: {request}")
        
        # Stage A: Vector Retrieval
        candidates = await self._retrieve_candidates(request)
        
        # Stage B: CPU Ranker
        ranked_candidates = await self._rank_candidates(request, candidates)
        
        # Stage C: LLM-as-judge Rerank (Stub)
        final_candidates = await self._judge_rerank(request, ranked_candidates)
        
        # Stage D: Constraints Re-ranking (Diversity)
        final_gifts_data = self._apply_final_rank_and_diversity(request, final_candidates)

        gifts = [
            GiftDTO(
                id=g.gift_id,
                title=g.title,
                description=g.description,
                price=g.price,
                currency=g.currency,
                image_url=g.image_url,
                product_url=g.product_url,
                merchant=g.merchant,
                category=g.category
            ) for g in final_gifts_data
        ]
        featured_gift = gifts[0] if gifts else None

        return RecommendationResponse(
            quiz_run_id="stub-id", # TODO: integrate with quiz_run repo
            engine_version=engine_version,
            featured_gift=featured_gift,
            gifts=gifts,
            debug={"status": "candidates_retrieved", "count": len(candidates)} if request.debug else None
        )

    def _build_query_text(self, request: RecommendationRequest) -> str:
        """Construct semantic search query from quiz answers."""
        parts = [
            f"Gift for {request.relationship or 'someone'}",
            f"Occasion: {request.occasion}" if request.occasion else "",
            f"Age: {request.recipient_age}",
            f"Gender: {request.recipient_gender}" if request.recipient_gender else "",
            f"Interests: {', '.join(request.interests)}" if request.interests else "",
            f"Description: {request.interests_description}" if request.interests_description else "",
            f"Vibe: {request.vibe}" if request.vibe else "",
        ]
        return " ".join([p for p in parts if p]).strip()

    async def _retrieve_candidates(self, request: RecommendationRequest) -> list[Any]:
        """Stage A: Vector Retrieval (pgvector)"""
        query_text = self._build_query_text(request)
        logger.info(f"Retrieving candidates for query: '{query_text}'")
        
        # 1. Generate Query Embedding
        query_vector = self.embedding_service.embed_batch([query_text])[0]
        
        # 2. Search in Repo (Top 50 candidates for further ranking)
        candidates = await self.repo.search_similar_products(
            embedding=query_vector, 
            limit=50,
            is_active_only=True
        )
        return candidates

    async def _rank_candidates(self, request: RecommendationRequest, candidates: list[Any]) -> list[Any]:
        """Stage B: CPU Ranker (Logic from SoT Section 5)"""
        return candidates

    async def _judge_rerank(self, request: RecommendationRequest, candidates: list[Any]) -> list[Any]:
        """Stage C: LLM-as-judge Rerank (Stub for now)"""
        return candidates

    def _apply_final_rank_and_diversity(self, request: RecommendationRequest, candidates: list[Any]) -> list[Any]:
        """Stage D: Constraints Re-ranking & Diversity"""
        return candidates[:request.top_n]
