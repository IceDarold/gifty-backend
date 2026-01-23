from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import and_, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Product, ProductEmbedding

logger = logging.getLogger(__name__)


class CatalogRepository(ABC):
    @abstractmethod
    async def upsert_products(self, products: list[dict]) -> int:
        """Upsert a batch of products returned by provider.
        Returns count of upserted items.
        """
        pass

    @abstractmethod
    async def get_active_products_count(self) -> int:
        pass

    @abstractmethod
    async def get_products_without_embeddings(self, model_version: str, limit: int = 100) -> list[dict]:
        pass

    @abstractmethod
    async def save_embeddings(self, embeddings: list[dict]) -> int:
        pass

    @abstractmethod
    async def get_products_without_llm_score(self, limit: int = 100) -> list[Product]:
        pass

    @abstractmethod
    async def save_llm_scores(self, scores: list[dict]) -> int:
        pass


    @abstractmethod
    async def mark_inactive_except(self, seen_ids: set[str]) -> int:
        """Mark products NOT in seen_ids as is_active=False. Returns count of modified rows."""
        pass


class PostgresCatalogRepository(CatalogRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_products(self, products: list[dict]) -> int:
        if not products:
            return 0

        # Construct values for upsert.
        # We assume products list contains dicts matching Product model fields.
        stmt = insert(Product).values(products)
        
        # On conflict do update
        # We update everything except created_at (and gift_id obviously)
        update_dict = {
            col.name: col
            for col in stmt.excluded
            if col.name not in ("created_at", "gift_id")
        }
        
        stmt = stmt.on_conflict_do_update(
            index_elements=[Product.gift_id],
            set_=update_dict
        )
        
        result = await self.session.execute(stmt)
        return result.rowcount

    async def mark_inactive_except(self, seen_ids: set[str]) -> int:
        """
        Mark all products NOT in the provided set of gift_ids as inactive.
        Used for soft-delete during full sync.
        """
        if not seen_ids:
            # If seen_ids is empty, we don't deactivate everything 
            # as it might be a failed sync. We require at least some IDs.
            return 0
            
        stmt = (
            update(Product)
            .where(Product.gift_id.notin_(seen_ids))
            .where(Product.is_active.is_(True))
            .values(is_active=False, updated_at=func.now())
        )
        
        result = await self.session.execute(stmt)
        return result.rowcount

    async def get_active_products_count(self) -> int:
        query = select(func.count(Product.gift_id)).where(Product.is_active.is_(True))
        result = await self.session.execute(query)
        return result.scalar() or 0

    async def get_products_without_embeddings(self, model_version: str, limit: int = 100) -> list[Product]:
        """
        Fetch products that do not have an embedding for the specified model_version.
        We check if `product_embeddings` entry exists OR if content_hash doesn't match.
        """
        from sqlalchemy.orm import aliased
        from sqlalchemy import and_, or_
        from app.models import ProductEmbedding
        
        p = aliased(Product)
        pe = aliased(ProductEmbedding)
        
        stmt = (
            select(p)
            .outerjoin(pe, p.gift_id == pe.gift_id)
            .where(
                and_(
                    p.is_active.is_(True),
                    or_(
                        pe.gift_id.is_(None),
                        pe.content_hash != p.content_hash,
                        pe.model_version != model_version
                    )
                )
            )
            .limit(limit)
        )
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def save_embeddings(self, embeddings: list[dict]) -> int:
        """
        Upsert product embeddings.
        embeddings list should contain dicts matching ProductEmbedding model.
        """
        if not embeddings:
            return 0
            
        stmt = insert(ProductEmbedding).values(embeddings)
        
        update_dict = {
            "embedding": stmt.excluded.embedding, # This assumes we pass vector/list
            "content_hash": stmt.excluded.content_hash,
            "embedded_at": func.now(),
            "updated_at": datetime.now(),
        }

        stmt = stmt.on_conflict_do_update(
            constraint="pk_product_embeddings", # Primary key constraint name
            set_=update_dict
        )

        try:
            result = await self.session.execute(stmt)
            return result.rowcount
        except Exception as e:
            logger.error(f"Failed to upsert embeddings. Batch size: {len(embeddings)}. Error: {type(e).__name__}: {e}")
            raise e

    async def search_similar_products(self, embedding: list[float], limit: int = 10, min_similarity: float = 0.0, is_active_only: bool = True) -> list[Product]:
        # Perform vector search using cosine distance (operator <=>)
        # Note: pgvector's cosine_distance returns distance (0..2), where 0 is identical.
        # Similarity = 1 - distance.
        # However, for sorting, smaller distance = higher similarity.
        
        stmt = (
            select(Product)
            .join(ProductEmbedding, Product.gift_id == ProductEmbedding.gift_id)
        )
        
        if is_active_only:
            stmt = stmt.where(Product.is_active.is_(True))
            
        stmt = stmt.order_by(ProductEmbedding.embedding.cosine_distance(embedding)).limit(limit)
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_products_without_llm_score(self, limit: int = 100) -> list[Product]:
        """
        Fetch products that don't have an LLM gift score yet.
        """
        stmt = (
            select(Product)
            .where(
                and_(
                    Product.is_active.is_(True),
                    Product.llm_gift_score.is_(None)
                )
            )
            .order_by(Product.updated_at.desc()) # Or some other priority
            .limit(limit)
        )
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def save_llm_scores(self, scores: list[dict]) -> int:
        """
        Update product rows with LLM scores and reasoning.
        scores list should contain dicts: {'gift_id': str, 'llm_gift_score': float, 'llm_gift_reasoning': str, ...}
        """
        if not scores:
            return 0
            
        # We can't use insert().on_conflict_do_update easily for multiple primary keys update if we only want to update.
        # But since gift_id is PK, we can use it.
        # Using a bulk update approach or a temporary table might be faster for large batches,
        # but for small scoring batches, we can use a simpler loop or a compiled statement.
        
        count = 0
        for score_data in scores:
            gift_id = score_data.pop("gift_id")
            score_data["llm_scored_at"] = func.now()
            
            stmt = (
                update(Product)
                .where(Product.gift_id == gift_id)
                .values(**score_data)
            )
            await self.session.execute(stmt)
            count += 1
            
        return count
