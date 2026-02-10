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
        stmt = select(ParsingSource).where(ParsingSource.id == source_id)
        result = await self.session.execute(stmt)
        source = result.scalar_one_or_none()
        
        if source:
            source.last_synced_at = func.now()
            source.next_sync_at = datetime.now() + timedelta(hours=source.refresh_interval_hours)
            source.status = "waiting"
            if source.config is None:
                source.config = {}
            cfg = dict(source.config)
            cfg["last_stats"] = stats
            source.config = cfg
            
        await self.session.commit()

    async def set_queued(self, source_id: int):
        stmt = update(ParsingSource).where(ParsingSource.id == source_id).values(
            status="running", # Use 'running' as soon as it's queued for simplicity? 
            # Or 'waiting' (for worker). Let's use 'running' to show activity.
            next_sync_at=datetime.now() + timedelta(minutes=30) # Temporary push to avoid re-scheduling
        )
        await self.session.execute(stmt)
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

    async def get_all_sources(self) -> Sequence[ParsingSource]:
        stmt = select(ParsingSource).order_by(ParsingSource.id.asc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def upsert_source(self, data: dict) -> ParsingSource:
        url = data.get("url")
        if not url:
            raise ValueError("URL is required")

        stmt = select(ParsingSource).where(ParsingSource.url == url)
        result = await self.session.execute(stmt)
        source = result.scalar_one_or_none()

        if source:
            for key, value in data.items():
                if hasattr(source, key):
                    setattr(source, key, value)
        else:
            source = ParsingSource(**data)
            self.session.add(source)
            
        await self.session.commit()
        await self.session.refresh(source)
        return source

    async def get_source_by_id(self, source_id: int) -> Optional[ParsingSource]:
        stmt = select(ParsingSource).where(ParsingSource.id == source_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def report_source_error(self, source_id: int, error_msg: str, is_broken: bool = True) -> Optional[ParsingSource]:
        stmt = select(ParsingSource).where(ParsingSource.id == source_id)
        result = await self.session.execute(stmt)
        source = result.scalar_one_or_none()
        
        if source:
            if source.config is None:
                source.config = {}
            source.config["last_error"] = error_msg
            source.config["fix_required"] = True
            if is_broken:
                source.is_active = False
                source.status = "broken"
            else:
                source.status = "error"
            
            await self.session.commit()
            return source
        return None

    async def sync_spiders(self, available_spiders: List[str]) -> List[str]:
        """
        Synchronizes the list of spiders from the scraper with the database.
        Returns a list of NEW spider keys that were not in the database.
        """
        stmt = select(ParsingSource.site_key)
        result = await self.session.execute(stmt)
        existing_keys = set(result.scalars().all())
        
        new_spiders = []
        for spider_key in available_spiders:
            if spider_key not in existing_keys:
                # Add new inactive source
                new_source = ParsingSource(
                    site_key=spider_key,
                    url=f"https://{spider_key}.placeholder", # Needs to be filled
                    type="hub",
                    strategy="discovery",
                    is_active=False,
                    config={"is_new": True, "note": "Automatically detected, please configure"}
                )
                self.session.add(new_source)
                new_spiders.append(spider_key)
        
        if new_spiders:
            await self.session.commit()
            
        return new_spiders

    async def set_source_active_status(self, source_id: int, is_active: bool) -> bool:
        stmt = update(ParsingSource).where(ParsingSource.id == source_id).values(
            is_active=is_active,
            status="waiting" if is_active else "disabled"
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0

    async def set_source_status(self, source_id: int, status: str):
        stmt = update(ParsingSource).where(ParsingSource.id == source_id).values(status=status)
        await self.session.execute(stmt)
        await self.session.commit()

    async def update_source_logs(self, source_id: int, logs: str):
        stmt = select(ParsingSource).where(ParsingSource.id == source_id)
        result = await self.session.execute(stmt)
        source = result.scalar_one_or_none()
        if source:
            if source.config is None:
                source.config = {}
            cfg = dict(source.config)
            cfg["last_logs"] = logs
            source.config = cfg
            await self.session.commit()

    async def reset_source_error(self, source_id: int):
        stmt = select(ParsingSource).where(ParsingSource.id == source_id)
        result = await self.session.execute(stmt)
        source = result.scalar_one_or_none()
        if source:
            if source.config is None:
                source.config = {}
            # Update dictionary directly as SQLAlchemy handles change tracking for JSONB
            cfg = dict(source.config)
            cfg.pop("last_error", None)
            cfg.pop("fix_required", None)
            source.config = cfg
            await self.session.commit()

    async def update_source(self, source_id: int, data: dict) -> Optional[ParsingSource]:
        stmt = select(ParsingSource).where(ParsingSource.id == source_id)
        result = await self.session.execute(stmt)
        source = result.scalar_one_or_none()
        
        if source:
            for key, value in data.items():
                if hasattr(source, key):
                    setattr(source, key, value)
            await self.session.commit()
            await self.session.refresh(source)
            return source
        return None

    async def log_parsing_run(self, source_id: int, status: str, items_scraped: int, items_new: int, error_message: str = None):
        from app.models import ParsingRun
        run = ParsingRun(
            source_id=source_id,
            status=status,
            items_scraped=items_scraped,
            items_new=items_new,
            error_message=error_message
        )
        self.session.add(run)
        await self.session.commit()

    async def get_source_history(self, source_id: int, limit: int = 15):
        from app.models import ParsingRun
        stmt = (
            select(ParsingRun)
            .where(ParsingRun.source_id == source_id)
            .order_by(ParsingRun.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_total_products_count(self, site_key: str) -> int:
        from app.models import Product, ParsingSource, ParsingRun
        # Approximate count based on gift_id prefix
        stmt = select(func.count()).select_from(Product).where(Product.gift_id.like(f"{site_key}:%"))
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def get_aggregate_status(self, site_key: str) -> str:
        """Returns 'running' if any source for this site is running, else 'waiting' or 'error'."""
        stmt = select(ParsingSource.status).where(ParsingSource.site_key == site_key)
        result = await self.session.execute(stmt)
        statuses = result.scalars().all()
        if "running" in statuses:
            return "running"
        if "error" in statuses:
            return "error"
        if "broken" in statuses:
            return "broken"
        return "waiting"

    async def get_aggregate_history(self, site_key: str, limit_days: int = 15):
        """Returns runs aggregated by day for the entire site."""
        from app.models import ParsingRun, ParsingSource
        # Aggregate by date (truncated created_at)
        date_trunc = func.date_trunc('day', ParsingRun.created_at)
        stmt = (
            select(
                date_trunc.label("day"),
                func.sum(ParsingRun.items_new).label("items_new"),
                func.sum(ParsingRun.items_scraped).label("items_scraped")
            )
            .join(ParsingSource, ParsingRun.source_id == ParsingSource.id)
            .where(ParsingSource.site_key == site_key)
            .group_by(date_trunc)
            .order_by(date_trunc.desc())
            .limit(limit_days)
        )
        result = await self.session.execute(stmt)
        return result.all()

    async def get_last_full_cycle_stats(self, site_key: str) -> int:
        """
        Calculates how many new items were added since the last 'discovery' run started.
        """
        from app.models import ParsingRun, ParsingSource
        # Find the last successful discovery run for this site
        last_hub_run_stmt = (
            select(ParsingRun.created_at)
            .join(ParsingSource, ParsingRun.source_id == ParsingSource.id)
            .where(ParsingSource.site_key == site_key)
            .where(ParsingSource.type == "hub")
            .order_by(ParsingRun.created_at.desc())
            .limit(1)
        )
        last_hub_run_res = await self.session.execute(last_hub_run_stmt)
        last_hub_time = last_hub_run_res.scalar()
        
        if not last_hub_time:
            return 0
            
        # Sum all new items since that time for this site_key
        stmt = (
            select(func.sum(ParsingRun.items_new))
            .join(ParsingSource, ParsingRun.source_id == ParsingSource.id)
            .where(ParsingSource.site_key == site_key)
            .where(ParsingRun.created_at >= last_hub_time)
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def get_total_category_products_count(self, site_key: str, category_name: str) -> int:
        from app.models import Product
        # Try to match by category name stored in Product.category
        stmt = select(func.count()).select_from(Product).where(
            and_(
                Product.gift_id.like(f"{site_key}:%"),
                Product.category == category_name
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def get_source_daily_history(self, source_id: int, limit_days: int = 15):
        from app.models import ParsingRun
        date_trunc = func.date_trunc('day', ParsingRun.created_at)
        stmt = (
            select(
                date_trunc.label("day"),
                func.sum(ParsingRun.items_new).label("items_new"),
                func.sum(ParsingRun.items_scraped).label("items_scraped")
            )
            .where(ParsingRun.source_id == source_id)
            .group_by(date_trunc)
            .order_by(date_trunc.desc())
            .limit(limit_days)
        )
        result = await self.session.execute(stmt)
        return result.all()
