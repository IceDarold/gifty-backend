from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Sequence

import sqlalchemy as sa
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
    async def mark_inactive_except(self, seen_ids: set[str]) -> int:
        """Mark products NOT in seen_ids as is_active=False. Returns count of modified rows."""
        pass

    @abstractmethod
    async def delete_products_by_site(self, site_key: str) -> int:
        """Hard delete all products for a specific site."""
        pass

    @abstractmethod
    async def get_products(
        self, 
        limit: int = 50, 
        offset: int = 0, 
        is_active: Optional[bool] = None,
        merchant: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None
    ) -> Sequence[Product]:
        pass

    @abstractmethod
    async def count_products(
        self, 
        is_active: Optional[bool] = None,
        merchant: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None
    ) -> int:
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
        # We update everything except created_at (and product_id obviously)
        update_dict = {
            col.name: col
            for col in stmt.excluded
            if col.name not in ("created_at", "product_id")
        }
        
        stmt = stmt.on_conflict_do_update(
            index_elements=[Product.product_id],
            set_=update_dict
        )

        # RETURNING xmax is specific to PostgreSQL for counting inserts vs updates
        if self.session.bind.dialect.name == "postgresql":
            stmt = stmt.returning(sa.literal_column("xmax"))
            result = await self.session.execute(stmt)
            rows = result.scalars().all()
            inserted_count = sum(1 for xmax in rows if xmax == 0)
            return inserted_count
        else:
            # Fallback for SQLite/others: just return rowcount
            result = await self.session.execute(stmt)
            return result.rowcount

    async def mark_inactive_except(self, seen_ids: set[str]) -> int:
        """
        Mark all products NOT in the provided set of product_ids as inactive.
        Used for soft-delete during full sync.
        """
        if not seen_ids:
            # If seen_ids is empty, we don't deactivate everything 
            # as it might be a failed sync. We require at least some IDs.
            return 0
            
        stmt = (
            update(Product)
            .where(Product.product_id.notin_(seen_ids))
            .where(Product.is_active.is_(True))
            .values(is_active=False, updated_at=func.now())
        )
        
        result = await self.session.execute(stmt)
        return result.rowcount

    async def delete_products_by_site(self, site_key: str) -> int:
        """Hard delete all products for a specific site."""
        stmt = sa.delete(Product).where(Product.product_id.like(f"{site_key}:%"))
        result = await self.session.execute(stmt)
        return result.rowcount

    async def get_active_products_count(self) -> int:
        query = select(func.count(Product.product_id)).where(Product.is_active.is_(True))
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
            .outerjoin(
                pe,
                and_(
                    p.product_id == pe.product_id,
                    pe.model_version == model_version
                )
            )
            .where(
                and_(
                    p.is_active.is_(True),
                    or_(
                        pe.product_id.is_(None),
                        pe.content_hash != p.content_hash
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
            index_elements=[
                ProductEmbedding.product_id,
                ProductEmbedding.model_name,
                ProductEmbedding.model_version
            ],
            set_=update_dict
        )

        try:
            result = await self.session.execute(stmt)
            return result.rowcount
        except Exception as e:
            logger.error(f"Failed to upsert embeddings. Batch size: {len(embeddings)}. Error: {type(e).__name__}: {e}")
            raise e

    async def search_similar_products(
        self, 
        embedding: list[float], 
        limit: int = 10, 
        min_similarity: float = 0.0, 
        is_active_only: bool = True,
        max_price: Optional[int] = None,
        max_delivery_days: Optional[int] = None,
        model_name: Optional[str] = None
    ) -> list[Product]:
        # Perform vector search using cosine distance (operator <=>)
        from app.core.logic_config import logic_config
        target_model = model_name or logic_config.llm.model_embedding
        
        stmt = (
            select(Product)
            .join(ProductEmbedding, and_(
                Product.product_id == ProductEmbedding.product_id,
                ProductEmbedding.model_name == target_model
            ))
        )
        
        if is_active_only:
            stmt = stmt.where(Product.is_active.is_(True))
            
        if max_price:
            stmt = stmt.where(Product.price <= max_price)
            
        if max_delivery_days:
            stmt = stmt.where(Product.delivery_days <= max_delivery_days)
            
        distance_col = ProductEmbedding.embedding.cosine_distance(embedding)
        
        if min_similarity > 0:
            # cosine_similarity = 1 - cosine_distance
            stmt = stmt.where(1 - distance_col >= min_similarity)
            
        stmt = stmt.order_by(distance_col).limit(limit)
        try:
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"CatalogRepository.search_similar_products failed: {e}")
            from app.services.notifications import get_notification_service
            notifier = get_notification_service()
            # Send alert
            if notifier:
                await notifier.notify(
                    topic="db_error",
                    message="Vector search failed in CatalogRepository",
                    data={"error": str(e)}
                )
            
            from app.config import get_settings
            if get_settings().env == "dev":
                logger.warning("DB search failed, returning empty list (dev mode)")
                return []
            raise e

    async def get_products(
        self, 
        limit: int = 50, 
        offset: int = 0, 
        is_active: Optional[bool] = None,
        merchant: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None
    ) -> Sequence[Product]:
        stmt = select(Product)
        if is_active is not None:
            stmt = stmt.where(Product.is_active == is_active)
        if merchant:
            stmt = stmt.where(Product.merchant == merchant)
        if category:
            stmt = stmt.where(Product.category == category)
        if search:
            stmt = stmt.where(Product.title.ilike(f"%{search}%"))
        
        stmt = stmt.order_by(Product.updated_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_products(
        self, 
        is_active: Optional[bool] = None,
        merchant: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None
    ) -> int:
        stmt = select(func.count(Product.product_id))
        if is_active is not None:
            stmt = stmt.where(Product.is_active == is_active)
        if merchant:
            stmt = stmt.where(Product.merchant == merchant)
        if category:
            stmt = stmt.where(Product.category == category)
        if search:
            stmt = stmt.where(Product.title.ilike(f"%{search}%"))
            
        result = await self.session.execute(stmt)
        return result.scalar() or 0
