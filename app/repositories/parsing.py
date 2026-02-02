from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional, List, Sequence

from sqlalchemy import select, update, and_, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ParsingSource, CategoryMap

class ParsingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_due_sources(self, limit: int = 10) -> Sequence[ParsingSource]:
        stmt = (
            select(ParsingSource)
            .where(
                and_(
                    ParsingSource.is_active.is_(True),
                    ParsingSource.next_sync_at <= func.now()
                )
            )
            .order_by(ParsingSource.priority.desc(), ParsingSource.next_sync_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update_source_stats(self, source_id: int, stats: dict):
        # Basic update logic, can be made smarter later (Smart Scheduling)
        stmt = select(ParsingSource).where(ParsingSource.id == source_id)
        result = await self.session.execute(stmt)
        source = result.scalar_one_or_none()
        
        if source:
            source.last_synced_at = func.now()
            # Default next sync based on fixed interval
            source.next_sync_at = datetime.now() + timedelta(hours=source.refresh_interval_hours)
            # We could store stats in a JSON field if needed
            if source.config is None:
                source.config = {}
            source.config["last_stats"] = stats
            
        await self.session.commit()

    async def get_or_create_category_maps(self, names: List[str]) -> List[CategoryMap]:
        if not names:
            return []
            
        # Bulk get existing
        stmt = select(CategoryMap).where(CategoryMap.external_name.in_(names))
        result = await self.session.execute(stmt)
        existing = {m.external_name: m for m in result.scalars().all()}
        
        new_names = [n for n in names if n not in existing]
        if new_names:
            # Bulk insert new ones
            insert_stmt = insert(CategoryMap).values([
                {"external_name": name, "internal_category_id": None}
                for name in new_names
            ]).on_conflict_do_nothing()
            await self.session.execute(insert_stmt)
            
            # Fetch again to get all (including newly created)
            stmt = select(CategoryMap).where(CategoryMap.external_name.in_(names))
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
            
        return list(existing.values())

    async def get_unmapped_categories(self, limit: int = 100) -> Sequence[CategoryMap]:
        """Возвращает категории, у которых еще нет привязки к внутренней категории Gifty."""
        stmt = (
            select(CategoryMap)
            .where(CategoryMap.internal_category_id.is_(None))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update_category_mappings(self, mappings: List[dict]) -> int:
        """
        Массово обновляет привязки внешних категорий к внутренним.
        mappings: [{"external_name": "...", "internal_category_id": 123}, ...]
        """
        if not mappings:
            return 0
        
        count = 0
        for m in mappings:
            stmt = (
                update(CategoryMap)
                .where(CategoryMap.external_name == m["external_name"])
                .values(internal_category_id=m["internal_category_id"])
            )
            await self.session.execute(stmt)
            count += 1
        
        await self.session.commit()
        return count
