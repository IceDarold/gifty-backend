from __future__ import annotations
from datetime import datetime, timedelta
import json
import logging
from typing import Optional, List, Sequence, Any

from sqlalchemy import select, update, and_, func, case
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ParsingSource, CategoryMap, ParsingRun, ParsingHub, DiscoveredCategory

logger = logging.getLogger(__name__)

class ParsingRepository:
    def __init__(self, session: AsyncSession, redis: Optional[Any] = None):
        self.session = session
        self.redis = redis

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
        """Marks source as queued in RabbitMQ. Status 'running' will be set by worker."""
        stmt = update(ParsingSource).where(ParsingSource.id == source_id).values(
            status="queued", 
            next_sync_at=datetime.now() + timedelta(minutes=15)
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def get_all_active_sources(self) -> Sequence[ParsingSource]:
        """Returns all sources that are currently active."""
        stmt = select(ParsingSource).where(ParsingSource.is_active.is_(True))
        result = await self.session.execute(stmt)
        return result.scalars().all()

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
            if self.session.bind.dialect.name == "postgresql":
                from sqlalchemy.dialects.postgresql import insert as pg_insert
                insert_stmt = pg_insert(CategoryMap).values([
                    {"external_name": name, "internal_category_id": None}
                    for name in new_names
                ]).on_conflict_do_nothing()
                await self.session.execute(insert_stmt)
            else:
                # SQLite fallback: manual loop or simple insert (ignoring conflicts if we already filtered)
                for name in new_names:
                    self.session.add(CategoryMap(external_name=name, internal_category_id=None))
                await self.session.flush()
            
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

    async def get_source(self, source_id: int) -> Optional[ParsingSource]:
        """Alias for get_source_by_id used by IngestionService."""
        return await self.get_source_by_id(source_id)

    async def report_source_error(self, source_id: int, error_msg: str, is_broken: bool = True) -> Optional[ParsingSource]:
        stmt = select(ParsingSource).where(ParsingSource.id == source_id)
        result = await self.session.execute(stmt)
        source = result.scalar_one_or_none()
        
        if source:
            if source.config is None:
                source.config = {}
            
            cfg = dict(source.config)
            cfg["last_error"] = error_msg
            
            # Simple retry logic: if it's not a discovery (hub) which we want to be more careful with,
            # or if it's discovery-deep, we can allow a few retries before marking as broken.
            retries = cfg.get("retry_count", 0)
            
            if is_broken or retries >= 3:
                cfg["fix_required"] = True
                source.is_active = False
                source.status = "broken"
                cfg["retry_count"] = 0 # reset for next manual fix
            else:
                cfg["retry_count"] = retries + 1
                source.status = "error"
                # Back-off: wait 10 mins * retries
                source.next_sync_at = datetime.now() + timedelta(minutes=10 * (retries + 1))
            
            source.config = cfg
            await self.session.commit()
            return source
        return None

    async def sync_spiders(self, available_spiders: List[str]) -> List[str]:
        """
        Synchronizes spiders with discovery hubs and keeps runtime hub sources for compatibility.
        """
        hub_stmt = select(ParsingHub.site_key)
        hub_result = await self.session.execute(hub_stmt)
        existing_hub_keys = set(hub_result.scalars().all())
        
        new_spiders = []
        for spider_key in available_spiders:
            if spider_key not in existing_hub_keys:
                self.session.add(
                    ParsingHub(
                        site_key=spider_key,
                        url=f"https://{spider_key}.placeholder",
                        strategy="discovery",
                        is_active=False,
                        status="waiting",
                        config={"is_new": True, "note": "Automatically detected, please configure"},
                    )
                )
                new_spiders.append(spider_key)

            # Runtime compatibility: keep one hub source entry for manual run/detail screens.
            src_stmt = select(ParsingSource).where(
                and_(ParsingSource.site_key == spider_key, ParsingSource.type == "hub")
            )
            src_res = await self.session.execute(src_stmt)
            existing_source = src_res.scalar_one_or_none()
            if not existing_source:
                self.session.add(
                    ParsingSource(
                        site_key=spider_key,
                        url=f"https://{spider_key}.placeholder",
                        type="hub",
                        strategy="discovery",
                        is_active=False,
                        config={"is_new": True, "note": "Runtime mirror of parsing_hubs"},
                    )
                )
        
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
        await self.session.refresh(run)
        return run

    async def create_parsing_run(
        self,
        source_id: int,
        status: str = "queued",
        items_scraped: int = 0,
        items_new: int = 0,
        error_message: str = None,
        duration_seconds: float | None = None,
        logs: str | None = None,
    ):
        from app.models import ParsingRun

        run = ParsingRun(
            source_id=source_id,
            status=status,
            items_scraped=items_scraped,
            items_new=items_new,
            error_message=error_message,
            duration_seconds=duration_seconds,
            logs=logs,
        )
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def update_parsing_run(
        self,
        run_id: int,
        *,
        status: str | None = None,
        items_scraped: int | None = None,
        items_new: int | None = None,
        error_message: str | None = None,
        duration_seconds: float | None = None,
        logs: str | None = None,
    ):
        from app.models import ParsingRun

        stmt = select(ParsingRun).where(ParsingRun.id == run_id)
        res = await self.session.execute(stmt)
        run = res.scalar_one_or_none()
        if not run:
            return None

        if status is not None:
            run.status = status
        if items_scraped is not None:
            run.items_scraped = items_scraped
        if items_new is not None:
            run.items_new = items_new
        if error_message is not None:
            run.error_message = error_message
        if duration_seconds is not None:
            run.duration_seconds = duration_seconds
        if logs is not None:
            run.logs = logs

        await self.session.commit()
        await self.session.refresh(run)
        return run

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
        # Approximate count based on product_id prefix
        stmt = select(func.count()).select_from(Product).where(Product.product_id.like(f"{site_key}:%"))
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def get_aggregate_status(self, site_key: str) -> str:
        """Returns 'running' if any source for this site is running, else 'waiting' or 'error'."""
        stmt = select(ParsingSource.status).where(ParsingSource.site_key == site_key)
        result = await self.session.execute(stmt)
        statuses = result.scalars().all()
        if "running" in statuses:
            return "running"
        if "queued" in statuses:
            return "queued"
        if "error" in statuses:
            return "error"
        if "broken" in statuses:
            return "broken"
        return "waiting"

    async def get_sites_monitoring(self) -> List[dict]:
        """Returns aggregate health and stats for all sites efficiently via SQL."""
        # This performs GROUP BY on database side
        # statuses per site
        stmt_stats = (
            select(
                ParsingSource.site_key,
                func.min(ParsingSource.id).label("first_id"),
                func.min(ParsingSource.url).label("first_url"),
                func.count(ParsingSource.id).label("total_sources"),
                func.sum(case((ParsingSource.status == 'running', 1), else_=0)).label("running_count"),
                func.sum(case((ParsingSource.status == 'queued', 1), else_=0)).label("queued_count"),
                func.sum(case((ParsingSource.status == 'error', 1), else_=0)).label("error_count"),
                func.sum(case((ParsingSource.status == 'broken', 1), else_=0)).label("broken_count"),
                func.max(ParsingSource.last_synced_at).label("last_synced_at")
            )
            .group_by(ParsingSource.site_key)
        )
        
        result = await self.session.execute(stmt_stats)
        rows = result.all()
        
        monitoring = []
        for row in rows:
            status = "waiting"
            if row.running_count > 0: status = "running"
            elif row.queued_count > 0: status = "queued"
            elif row.error_count > 0: status = "error"
            elif row.broken_count > 0: status = "broken"
            
            monitoring.append({
                "id": row.first_id,
                "site_key": row.site_key,
                "url": row.first_url,
                "total_sources": row.total_sources,
                "status": status,
                "last_synced_at": row.last_synced_at.isoformat() if row.last_synced_at else None,
                "is_active": True # Simplified for summary
            })
        return monitoring

    async def get_24h_stats(self) -> dict:
        """Returns scraped items count for the last 24h from DB ParsingRuns."""
        since = datetime.now() - timedelta(hours=24)
        stmt = select(
            func.sum(ParsingRun.items_scraped).label("scraped"),
            func.sum(ParsingRun.items_new).label("new")
        ).where(ParsingRun.created_at >= since)
        
        result = await self.session.execute(stmt)
        row = result.one_or_none()
        return {
            "scraped_24h": int(row.scraped or 0) if row else 0,
            "new_24h": int(row.new or 0) if row else 0
        }

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
        from app.models import DiscoveredCategory, ProductCategoryLink
        # Prefer discovered_categories linkage if possible; fallback remains approximate by name.
        cat = (
            await self.session.execute(
                select(DiscoveredCategory).where(
                    DiscoveredCategory.site_key == site_key,
                    DiscoveredCategory.name == category_name,
                )
            )
        ).scalar_one_or_none()
        if not cat:
            return 0
        stmt = select(func.count()).select_from(ProductCategoryLink).where(ProductCategoryLink.discovered_category_id == cat.id)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def get_or_create_merchant(self, site_key: str):
        from app.models import Merchant
        key = str(site_key or "").strip()
        if not key:
            return None

        existing = (
            await self.session.execute(select(Merchant).where(Merchant.site_key == key))
        ).scalar_one_or_none()
        if existing:
            return existing

        merchant = Merchant(site_key=key, name=key)
        self.session.add(merchant)
        await self.session.flush()
        return merchant

    async def upsert_product_category_links(
        self,
        *,
        product_ids: set[str],
        discovered_category_id: int,
        source_id: int,
        run_id: int | None = None,
    ) -> int:
        from sqlalchemy.dialects.postgresql import insert
        from app.models import ProductCategoryLink

        if not product_ids:
            return 0
        now = datetime.now()
        rows = [
            {
                "product_id": pid,
                "discovered_category_id": int(discovered_category_id),
                "source_id": int(source_id),
                "last_run_id": int(run_id) if run_id else None,
                "first_seen_at": now,
                "last_seen_at": now,
                "seen_count": 1,
            }
            for pid in product_ids
        ]
        stmt = insert(ProductCategoryLink).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=[ProductCategoryLink.product_id, ProductCategoryLink.discovered_category_id],
            set_={
                "source_id": stmt.excluded.source_id,
                "last_run_id": stmt.excluded.last_run_id,
                "last_seen_at": stmt.excluded.last_seen_at,
                "seen_count": ProductCategoryLink.seen_count + 1,
                "updated_at": func.now(),
            },
        )
        res = await self.session.execute(stmt)
        return res.rowcount or 0

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

    async def get_active_workers(self) -> List[dict]:
        """Fetches active workers from Redis heartbeats."""
        if not self.redis:
            return []
            
        workers = []
        try:
            keys = await self.redis.keys("worker_heartbeat:*")
            for key in keys:
                data = await self.redis.get(key)
                if data:
                    workers.append(json.loads(data))
        except Exception as e:
            logger.error(f"Error fetching workers from Redis: {e}")
        return workers

    async def get_source_by_url(self, url: str) -> Optional[ParsingSource]:
        stmt = select(ParsingSource).where(ParsingSource.url == url)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_hub_by_site_key(self, site_key: str) -> Optional[ParsingHub]:
        stmt = select(ParsingHub).where(ParsingHub.site_key == site_key)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_discovered_category_by_site_url(self, site_key: str, url: str) -> Optional[DiscoveredCategory]:
        stmt = select(DiscoveredCategory).where(
            and_(
                DiscoveredCategory.site_key == site_key,
                DiscoveredCategory.url == url,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_discovered_category(self, data: dict) -> DiscoveredCategory:
        site_key = data["site_key"]
        url = data["url"]
        category = await self.get_discovered_category_by_site_url(site_key, url)

        if category:
            for key, value in data.items():
                if hasattr(category, key) and value is not None:
                    setattr(category, key, value)
            await self.session.flush()
            return category

        category = DiscoveredCategory(**data)
        self.session.add(category)
        await self.session.flush()
        return category

    async def promote_discovered_category(self, category_id: int) -> Optional[ParsingSource]:
        stmt = select(DiscoveredCategory).where(DiscoveredCategory.id == category_id)
        result = await self.session.execute(stmt)
        category = result.scalar_one_or_none()
        if not category:
            return None

        src_stmt = select(ParsingSource).where(
            and_(
                ParsingSource.site_key == category.site_key,
                ParsingSource.url == category.url,
                ParsingSource.type == "list",
            )
        )
        src_res = await self.session.execute(src_stmt)
        source = src_res.scalar_one_or_none()

        if source is None:
            source = ParsingSource(
                url=category.url,
                type="list",
                site_key=category.site_key,
                strategy="deep",
                priority=50,
                refresh_interval_hours=24,
                is_active=True,
                status="waiting",
                category_id=category.id,
                config={
                    "discovery_name": category.name,
                    "parent_url": category.parent_url,
                    "discovered_category_id": category.id,
                },
            )
            self.session.add(source)
            await self.session.flush()
        else:
            source.is_active = True
            source.status = "waiting"
            source.category_id = category.id
            cfg = dict(source.config or {})
            if category.name:
                cfg["discovery_name"] = category.name
            if category.parent_url:
                cfg["parent_url"] = category.parent_url
            cfg["discovered_category_id"] = category.id
            source.config = cfg
            await self.session.flush()

        category.state = "promoted"
        category.promoted_source_id = source.id
        await self.session.flush()
        return source

    async def get_discovered_categories(self, limit: int = 50, states: Optional[List[str]] = None) -> List[DiscoveredCategory]:
        stmt = select(DiscoveredCategory)
        if states:
            stmt = stmt.where(DiscoveredCategory.state.in_(states))
        stmt = stmt.order_by(DiscoveredCategory.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_promoted_categories_today(self) -> int:
        stmt = select(func.count(DiscoveredCategory.id)).where(
            and_(
                DiscoveredCategory.state == "promoted",
                DiscoveredCategory.updated_at >= func.now() - timedelta(days=1),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def count_discovered_today(self) -> int:
        """Backward-compatible alias: number of promoted categories for last 24h."""
        return await self.count_promoted_categories_today()

    async def get_discovered_sources(self, limit: int = 50) -> List[ParsingSource]:
        """
        Backward-compatible alias:
        returns promoted runtime sources for new backlog semantics.
        Prefer get_discovered_categories() in new code.
        """
        categories = await self.get_discovered_categories(limit=limit, states=["new"])
        source_ids = [c.promoted_source_id for c in categories if c.promoted_source_id]
        if not source_ids:
            return []
        stmt = select(ParsingSource).where(ParsingSource.id.in_(source_ids))
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def activate_sources(self, source_ids: List[int]):
        """Backward-compatible alias: promotes discovered_categories by their ids."""
        if not source_ids:
            return 0
        promoted = 0
        for category_id in source_ids:
            source = await self.promote_discovered_category(category_id)
            if source:
                source.next_sync_at = func.now()
                promoted += 1
        await self.session.commit()
        return promoted
