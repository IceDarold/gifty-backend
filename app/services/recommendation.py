from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas_v2 import RecommendationRequest, RecommendationResponse, GiftDTO
from app.repositories.catalog import PostgresCatalogRepository

from app.services.embeddings import EmbeddingService
from app.services.intelligence import IntelligenceAPIClient, get_intelligence_client
from app.services.notifications import get_notification_service

from app.models import SearchLog, HypothesisProductLink
import uuid
import statistics
import time

logger = logging.getLogger(__name__)


class RecommendationService:
    def __init__(self, session: AsyncSession, embedding_service: EmbeddingService):
        self.session = session
        self.repo = PostgresCatalogRepository(session)
        self.embedding_service = embedding_service
        self.intelligence_client = get_intelligence_client()

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
        query_vector = await self.embedding_service.embed_batch_async([query_text])
        query_vector = query_vector[0]
        
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

    async def find_preview_products(
        self, 
        search_queries: List[str], 
        hypothesis_title: str = "", 
        max_price: Optional[int] = None,
        session_id: Optional[str] = None,
        hypothesis_id: Optional[uuid.UUID] = None,
        track_title: Optional[str] = None,
        llm_model: Optional[str] = None,
        search_context: str = "preview",
        limit_per_query: Optional[int] = None
    ) -> List[GiftDTO]:
        """
        Advanced retrieval for previews:
        1. Flexible budget (max_price + margin from logic_config)
        2. Parallel multi-query vector search
        3. Global reranking and Interleaving
        """
        from app.core.logic_config import logic_config
        
        # Override config with parameter if provided
        final_limit_per_query = limit_per_query or logic_config.items_per_query
        target_queries = search_queries[:logic_config.max_queries_for_preview]
        
        # 1. Flexible Budget
        effective_max_price = None
        if max_price:
            effective_max_price = int(max_price * (1 + logic_config.budget_margin_fraction))
            
        # 2. Parallel Vector Search for all queries
        async def _fetch_for_query(query: str):
            query_vectors = await self.embedding_service.embed_batch_async([query])
            if not query_vectors:
                return query, []
            
            candidates = await self.repo.search_similar_products(
                embedding=query_vectors[0],
                limit=logic_config.rerank_candidate_limit,
                is_active_only=True,
                max_price=effective_max_price
            )
            return query, candidates

        search_tasks = [_fetch_for_query(q) for q in target_queries]
        search_results_raw = await asyncio.gather(*search_tasks, return_exceptions=True)
        
        search_results = []
        for res in search_results_raw:
            if isinstance(res, Exception):
                logger.error(f"Search task failed in find_preview_products: {res}")
            else:
                search_results.append(res)
        
        # Map queries to their candidates and gather ALL unique candidates for reranking
        query_to_results = {}
        all_unique_candidates = {}
        
        # LOGGING: Track coverage for each query
        for res in search_results:
            if isinstance(res, tuple):
                query, candidates = res
                query_to_results[query] = candidates
                
                # Calculate simple metrics for logging
                results_count = len(candidates)
                top_sim = 0.0
                avg_sim = 0.0
                top_id = None
                
                if candidates:
                    # In vector search similarity is not directly in Product model, 
                    # but we can log that it found results.
                    # If we had access to the raw similarity scores from the repo, we'd log them here.
                    top_id = candidates[0].gift_id
                
                # Create SearchLog entry
                try:
                    log_entry = SearchLog(
                        session_id=session_id,
                        hypothesis_id=hypothesis_id,
                        track_title=track_title,
                        hypothesis_title=hypothesis_title,
                        search_context=search_context,
                        llm_model=llm_model or logic_config.model_smart,
                        search_query=query,
                        results_count=results_count,
                        predicted_category=track_title, # Topic serves as the predicted category
                        top_gift_id=top_id,
                        max_price=max_price,
                        engine_version="advanced_v1"
                    )
                    self.session.add(log_entry)
                except Exception as e:
                    logger.warning(f"Failed to log search result: {e}")

                for c in candidates:
                    if c.gift_id not in all_unique_candidates:
                        all_unique_candidates[c.gift_id] = c
        
        candidates_list = list(all_unique_candidates.values())
        if not candidates_list:
            return []

        # 3. Global Reranking
        doc_texts = [f"{c.title} {c.description or ''}" for c in candidates_list]
        query_context = hypothesis_title or " ".join(target_queries[:2])
        
        try:
            scores = await self.intelligence_client.rerank(query_context, doc_texts)
            id_to_score = {c.gift_id: score for c, score in zip(candidates_list, scores)}
        except Exception as e:
            logger.error(f"RecommendationService: Reranking failed, falling back to vector scores: {e}")
            # Proactive notification
            notifier = get_notification_service()
            await notifier.notify(
                topic="intelligence_error",
                message=f"Reranking failed for hypothesis: {hypothesis_title}",
                data={"error": str(e), "doc_count": len(doc_texts)}
            )
            # Fallback: assign scores based on original retrieval order to maintain some ranking
            id_to_score = {c.gift_id: (1.0 - (idx / len(candidates_list))) for idx, c in enumerate(candidates_list)}

        # 4. Filter, Sort and pick Top N per query
        per_query_final = []
        for query in target_queries:
            candidates = query_to_results.get(query, [])
            scored = sorted(candidates, key=lambda x: id_to_score.get(x.gift_id, 0.0), reverse=True)
            per_query_final.append(scored[:final_limit_per_query])

        # 5. Interleave with Deduplication
        final_list = []
        seen_ids = set()
        
        for i in range(final_limit_per_query):
            for q_list in per_query_final:
                if i < len(q_list):
                    p = q_list[i]
                    if p.gift_id not in seen_ids:
                        seen_ids.add(p.gift_id)
                        final_list.append(GiftDTO(
                            id=p.gift_id,
                            title=p.title,
                            description=p.description,
                            price=float(p.price) if p.price else None,
                            currency=p.currency or "RUB",
                            image_url=p.image_url,
                            product_url=p.product_url,
                            merchant=p.merchant,
                            category=p.category
                        ))
        
        # 6. Create HypothesisProductLink entries for the final list
        if hypothesis_id:
            try:
                for idx, gift_dto in enumerate(final_list[:10]): # Log top 10 shown products
                    link = HypothesisProductLink(
                        hypothesis_id=hypothesis_id,
                        gift_id=gift_dto.id,
                        similarity_score=id_to_score.get(gift_dto.id, 0.0), # Use reranker score if available
                        rank_position=idx + 1,
                        was_shown=True
                    )
                    self.session.add(link)
            except Exception as e:
                logger.warning(f"Failed to link products to hypothesis in find_preview_products: {e}")

        return final_list

    async def get_deep_dive_products(
        self, 
        search_queries: List[str], 
        hypothesis_title: str,
        hypothesis_description: str,
        max_price: Optional[int] = None,
        session_id: Optional[str] = None,
        hypothesis_id: Optional[uuid.UUID] = None,
        track_title: Optional[str] = None,
        llm_model: Optional[str] = None,
        limit: int = 15
    ) -> List[GiftDTO]:
        """
        Stage E: Deep Dive - Multi-query expansion + Reranking.
        """
        logger.info(f"Deep dive for hypothesis: {hypothesis_title}")
        
        # 1. Multi-query search (Parallel)
        from app.core.logic_config import logic_config
        effective_max_price = None
        if max_price:
            effective_max_price = int(max_price * (1 + logic_config.budget_margin_fraction))

        async def _search_one(query: str):
            query_vectors = await self.embedding_service.embed_batch_async([query])
            if not query_vectors:
                return []
            return await self.repo.search_similar_products(
                embedding=query_vectors[0],
                limit=15,
                is_active_only=True,
                max_price=effective_max_price
            )

        search_tasks = [_search_one(q) for q in search_queries[:3]]
        search_results_raw = await asyncio.gather(*search_tasks, return_exceptions=True)
        
        search_results = []
        for res in search_results_raw:
            if isinstance(res, Exception):
                logger.error(f"Search task failed in get_deep_dive_products: {res}")
            else:
                search_results.append(res)
        
        all_candidates = {}
        for results in search_results:
            for c in results:
                if c.gift_id not in all_candidates:
                    all_candidates[c.gift_id] = c
        
        candidates_list = list(all_candidates.values())
        if not candidates_list:
            # Log zero results for all queries
            for q in search_queries[:3]:
                 self.session.add(SearchLog(
                     search_query=q,
                     results_count=0,
                     predicted_category=track_title,
                     engine_version="deep_dive_v1"
                 ))
            return []

        # LOGGING: Log aggregate for deep dive
        for q in search_queries[:3]:
            self.session.add(SearchLog(
                session_id=session_id,
                hypothesis_id=hypothesis_id,
                track_title=track_title,
                hypothesis_title=hypothesis_title,
                search_context="deep_dive",
                llm_model=llm_model or logic_config.model_smart,
                search_query=q,
                results_count=len(search_results[0]) if len(search_results) > 0 else 0,
                predicted_category=track_title,
                max_price=max_price,
                engine_version="advanced_v1"
            ))

        # 2. Reranking
        doc_texts = [f"{c.title} {c.description or ''}" for c in candidates_list]
        query_context = f"{hypothesis_title} {hypothesis_description}"
        
        try:
            scores = await self.intelligence_client.rerank(query_context, doc_texts)
            id_to_score = {c.gift_id: score for c, score in zip(candidates_list, scores)}
        except Exception as e:
            logger.error(f"RecommendationService: Deep dive reranking failed, falling back to vector order: {e}")
            # Proactive notification
            notifier = get_notification_service()
            await notifier.notify(
                topic="intelligence_error",
                message=f"Deep dive reranking failed for: {hypothesis_title}",
                data={"error": str(e)}
            )
            id_to_score = {c.gift_id: (1.0 - (idx / len(candidates_list))) for idx, c in enumerate(candidates_list)}
        
        # Sort candidates list based on scores
        candidates_list.sort(key=lambda x: id_to_score.get(x.gift_id, 0.0), reverse=True)
        scored_products = candidates_list[:limit]
        
        # 3. Final DTO conversion
        results = []
        for p in scored_products:
            results.append(GiftDTO(
                id=p.gift_id,
                title=p.title,
                description=p.description,
                price=float(p.price) if p.price else None,
                currency=p.currency or "RUB",
                image_url=p.image_url,
                product_url=p.product_url,
                merchant=p.merchant,
                category=p.category
            ))
            
        return results
