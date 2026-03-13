from __future__ import annotations
from datetime import datetime, timedelta
import json
import logging
from typing import Optional, List, Sequence, Any

from sqlalchemy import select, update, and_, or_, func, case
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ParsingSource, CategoryMap, ParsingRun, ParsingHub, DiscoveredCategory
from app.outbox import enqueue_outbox_event

logger = logging.getLogger(__name__)

class ParsingRepository:
    def __init__(self, session: AsyncSession, redis: Optional[Any] = None):
        self.session = session
        self.redis = redis


    def _source_payload(self, source: ParsingSource) -> dict:
        return {
            "id": source.id,
            "site_key": source.site_key,
            "url": source.url,
            "status": source.status,
            "is_active": source.is_active,
            "type": source.type,
            "strategy": source.strategy,
            "priority": source.priority,
            "refresh_interval_hours": source.refresh_interval_hours,
            "last_synced_at": source.last_synced_at.isoformat() if source.last_synced_at else None,
            "next_sync_at": source.next_sync_at.isoformat() if source.next_sync_at else None,
            "category_id": source.category_id,
            "config": source.config,
            "updated_at": source.updated_at.isoformat() if getattr(source, "updated_at", None) else None,
            "created_at": source.created_at.isoformat() if getattr(source, "created_at", None) else None,
        }

    async def _emit_source_event(self, source: ParsingSource, event_type: str = "source.updated") -> None:
        await enqueue_outbox_event(
            self.session,
            aggregate_type="source",
            aggregate_id=str(source.id),
            event_type=event_type,
            payload=self._source_payload(source),
        )

    def _category_payload(self, category: DiscoveredCategory) -> dict:
        return {
            "id": category.id,
            "hub_id": category.hub_id,
            "site_key": category.site_key,
            "url": category.url,
            "name": category.name,
            "parent_url": category.parent_url,
            "state": category.state,
            "promoted_source_id": category.promoted_source_id,
            "meta": category.meta,
            "created_at": category.created_at.isoformat() if getattr(category, "created_at", None) else None,
            "updated_at": category.updated_at.isoformat() if getattr(category, "updated_at", None) else None,
        }

    async def _emit_category_event(self, category: DiscoveredCategory, event_type: str = "category.updated") -> None:
        await enqueue_outbox_event(
            self.session,
            aggregate_type="category",
            aggregate_id=str(category.id),
            event_type=event_type,
            payload=self._category_payload(category),
        )

    async def get_due_sources(self, limit: int = 10) -> Sequence[ParsingSource]:
        stmt = (
            select(ParsingSource)
            .outerjoin(ParsingHub, ParsingHub.site_key == ParsingSource.site_key)
            .where(
                and_(
                    ParsingSource.is_active.is_(True),
                    ParsingSource.next_sync_at <= func.now(),
                    or_(ParsingHub.id.is_(None), ParsingHub.status != "missing"),
                )
            )
            .order_by(ParsingSource.priority.desc(), ParsingSource.next_sync_at.asc())
            .limit(limit)
            # Postgres does not allow `FOR UPDATE` on the nullable side of an OUTER JOIN.
            # We only need to lock the due `parsing_sources` rows.
            .with_for_update(skip_locked=True, of=ParsingSource)
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
            await self._emit_source_event(source, "source.updated")

        await self.session.commit()

    async def set_queued(self, source_id: int):
        """Marks source as queued in RabbitMQ. Status 'running' will be set by worker."""
        # Avoid a race where the worker starts quickly and reports `running` before we persist `queued`.
        stmt = (
            update(ParsingSource)
            .where(ParsingSource.id == source_id, ParsingSource.status != "running")
            .values(
                status="queued",
                next_sync_at=datetime.now() + timedelta(minutes=15),
            )
        )
        await self.session.execute(stmt)
        source = (await self.session.execute(select(ParsingSource).where(ParsingSource.id == source_id))).scalar_one_or_none()
        if source:
            await self._emit_source_event(source, "source.updated")
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

    async def get_all_active_sources(self) -> Sequence[ParsingSource]:
        stmt = (
            select(ParsingSource)
            .where(ParsingSource.is_active.is_(True))
            .order_by(ParsingSource.id.asc())
        )
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
            await self.session.flush()
            await self._emit_source_event(source, "source.updated")
        else:
            source = ParsingSource(**data)
            self.session.add(source)
            await self.session.flush()
            await self._emit_source_event(source, "source.created")

        await self.session.commit()
        await self.session.refresh(source)
        return source

    async def get_or_create_discovered_category(
        self,
        *,
        site_key: str,
        url: str,
        name: str | None = None,
        parent_url: str | None = None,
    ):
        """
        Ensures a discovered_categories row exists for this (site_key, url).
        Used to satisfy the invariant: parsing_sources(type='list') requires category_id.
        """
        from app.models import DiscoveredCategory

        stmt = select(DiscoveredCategory).where(
            and_(DiscoveredCategory.site_key == site_key, DiscoveredCategory.url == url)
        )
        existing = (await self.session.execute(stmt)).scalar_one_or_none()
        if existing:
            # Best-effort enrichment.
            changed = False
            if name and not existing.name:
                existing.name = name
                changed = True
            if parent_url and not existing.parent_url:
                existing.parent_url = parent_url
                changed = True
            if changed:
                await self.session.flush()
                await self._emit_category_event(existing, "category.updated")
            return existing

        cat = DiscoveredCategory(
            site_key=site_key,
            url=url,
            name=name,
            parent_url=parent_url,
            state="new",
        )
        self.session.add(cat)
        await self.session.flush()
        await self._emit_category_event(cat, "category.created")
        return cat

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
            await self._emit_source_event(source, "source.updated")
            await self.session.commit()
            return source
        return None

    async def sync_spiders(
        self,
        available_spiders: List[str],
        *,
        default_urls: Optional[dict[str, str]] = None,
        seen_at: Optional[datetime] = None,
    ) -> List[str]:
        """
        Synchronizes spiders with discovery hubs and keeps runtime hub sources for compatibility.
        """
        default_urls = default_urls or {}
        seen_at = seen_at or datetime.now()
        normalized_spiders = [
            str(s).strip()
            for s in (available_spiders or [])
            if isinstance(s, str) and str(s).strip()
        ]

        if not normalized_spiders:
            return []

        # Batch load existing hubs for these spiders (remote DB latency makes per-spider queries too slow).
        hubs = (
            await self.session.execute(
                select(ParsingHub).where(ParsingHub.site_key.in_(normalized_spiders))
            )
        ).scalars().all()
        hub_by_key = {h.site_key: h for h in hubs if h.site_key}

        # Batch load hub mirror sources.
        hub_sources = (
            await self.session.execute(
                select(ParsingSource).where(
                    and_(
                        ParsingSource.site_key.in_(normalized_spiders),
                        ParsingSource.type == "hub",
                    )
                )
            )
        ).scalars().all()
        hub_source_by_key = {s.site_key: s for s in hub_sources if s.site_key}

        new_spiders: list[str] = []
        for spider_key in normalized_spiders:
            default_url = default_urls.get(spider_key)
            if isinstance(default_url, str):
                default_url = default_url.strip()
                if not default_url.startswith("http"):
                    default_url = None
            else:
                default_url = None

            hub = hub_by_key.get(spider_key)
            if not hub:
                self.session.add(
                    ParsingHub(
                        site_key=spider_key,
                        url=default_url or f"https://{spider_key}.placeholder",
                        strategy="discovery",
                        is_active=False,
                        status="waiting",
                        config={
                            "is_new": True,
                            "note": "Automatically detected, please configure",
                            "last_seen_in_code_at": seen_at.isoformat(),
                        },
                    )
                )
                new_spiders.append(spider_key)
            else:
                if default_url and isinstance(hub.url, str) and hub.url.endswith(".placeholder"):
                    hub.url = default_url
                cfg = dict(hub.config or {})
                cfg["last_seen_in_code_at"] = seen_at.isoformat()
                cfg.pop("missing_in_code", None)
                cfg.pop("missing_in_code_since", None)
                cfg.pop("missing_in_code_last_seen_at", None)
                hub.config = cfg
                if str(hub.status or "").strip() == "missing":
                    hub.status = "waiting"

            # Runtime compatibility: keep one hub source entry for manual run/detail screens.
            existing_source = hub_source_by_key.get(spider_key)
            if not existing_source:
                self.session.add(
                    ParsingSource(
                        site_key=spider_key,
                        url=default_url or f"https://{spider_key}.placeholder",
                        type="hub",
                        strategy="discovery",
                        is_active=False,
                        config={
                            "is_new": True,
                            "note": "Runtime mirror of parsing_hubs",
                            "last_seen_in_code_at": seen_at.isoformat(),
                        },
                    )
                )
            elif default_url and isinstance(existing_source.url, str) and existing_source.url.endswith(".placeholder"):
                existing_source.url = default_url
                cfg = dict(existing_source.config or {})
                cfg["last_seen_in_code_at"] = seen_at.isoformat()
                cfg.pop("missing_in_code", None)
                cfg.pop("missing_in_code_since", None)
                cfg.pop("missing_in_code_last_seen_at", None)
                # Auto-restore if we previously disabled due to missing in code.
                if cfg.get("disabled_due_to_missing_in_code"):
                    prev_active = cfg.get("disabled_due_to_missing_prev_is_active")
                    prev_status = cfg.get("disabled_due_to_missing_prev_status")
                    if isinstance(prev_active, bool):
                        existing_source.is_active = prev_active
                    if isinstance(prev_status, str) and prev_status:
                        existing_source.status = prev_status
                    cfg.pop("disabled_due_to_missing_in_code", None)
                    cfg.pop("disabled_due_to_missing_prev_is_active", None)
                    cfg.pop("disabled_due_to_missing_prev_status", None)
                    cfg.pop("disabled_due_to_missing_at", None)
                existing_source.config = cfg
            else:
                cfg = dict(existing_source.config or {})
                cfg["last_seen_in_code_at"] = seen_at.isoformat()
                cfg.pop("missing_in_code", None)
                cfg.pop("missing_in_code_since", None)
                cfg.pop("missing_in_code_last_seen_at", None)
                # Auto-restore if we previously disabled due to missing in code.
                if cfg.get("disabled_due_to_missing_in_code"):
                    prev_active = cfg.get("disabled_due_to_missing_prev_is_active")
                    prev_status = cfg.get("disabled_due_to_missing_prev_status")
                    if isinstance(prev_active, bool):
                        existing_source.is_active = prev_active
                    if isinstance(prev_status, str) and prev_status:
                        existing_source.status = prev_status
                    cfg.pop("disabled_due_to_missing_in_code", None)
                    cfg.pop("disabled_due_to_missing_prev_is_active", None)
                    cfg.pop("disabled_due_to_missing_prev_status", None)
                    cfg.pop("disabled_due_to_missing_at", None)
                existing_source.config = cfg

        await self.session.flush()
        hub_sources_updated = (
            await self.session.execute(
                select(ParsingSource).where(
                    and_(
                        ParsingSource.site_key.in_(normalized_spiders),
                        ParsingSource.type == "hub",
                    )
                )
            )
        ).scalars().all()
        for src in hub_sources_updated:
            await self._emit_source_event(src, "source.updated")
        await self.session.commit()
            
        return new_spiders

    async def mark_missing_spiders(
        self,
        available_spiders: List[str],
        *,
        grace_minutes: int = 360,
        now: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """
        Marks spiders that exist in DB but are missing from the codebase.

        This does NOT delete anything. It "quarantines" missing spiders:
        - adds flags into ParsingHub.config / ParsingSource.config (hub mirror)
        - after a grace period, disables all parsing_sources for that site_key so scheduler won't queue them.

        Why grace period:
        - during rolling deploy, an older worker image might report a partial spider list.
        """
        now = now or datetime.now()
        grace_minutes = max(0, int(grace_minutes or 0))
        available = {s for s in (available_spiders or []) if isinstance(s, str) and s.strip()}

        if available:
            hubs = (
                await self.session.execute(
                    select(ParsingHub)
                    .where(ParsingHub.site_key.notin_(list(available)))
                    .order_by(ParsingHub.site_key.asc())
                )
            ).scalars().all()
        else:
            hubs = (
                await self.session.execute(
                    select(ParsingHub).order_by(ParsingHub.site_key.asc())
                )
            ).scalars().all()

        hub_by_key = {h.site_key: h for h in hubs if h.site_key}
        missing_keys = sorted(hub_by_key.keys())

        newly_missing: list[str] = []
        for key in missing_keys:
            hub = hub_by_key.get(key)
            if not hub:
                continue
            cfg = dict(hub.config or {})
            if not cfg.get("missing_in_code"):
                newly_missing.append(key)
            cfg["missing_in_code"] = True
            cfg.setdefault("missing_in_code_since", now.isoformat())
            cfg["missing_in_code_last_seen_at"] = now.isoformat()
            hub.config = cfg
            hub.is_active = False
            if str(hub.status or "").strip() != "disabled":
                hub.status = "missing"

        # NOTE: We intentionally do NOT bulk-disable all sources here.
        # Disabling all list sources can be extremely expensive (many rows) and can stall workers.
        # Scheduler skips sources for missing spiders by joining ParsingHub status/config.
        disabled: list[str] = []

        # UI/Operator friendliness: immediately mark hub-mirror sources as missing (inactive),
        # even before grace disables all sources. This makes it visible in the parsers UI.
        if missing_keys:
            hub_sources = (
                await self.session.execute(
                    select(ParsingSource).where(
                        and_(ParsingSource.site_key.in_(missing_keys), ParsingSource.type == "hub")
                    )
                )
            ).scalars().all()
            for s in hub_sources:
                cfg = dict(s.config or {})
                cfg["missing_in_code"] = True
                cfg.setdefault("missing_in_code_since", now.isoformat())
                cfg["missing_in_code_last_seen_at"] = now.isoformat()
                # Only flip active->inactive for UI if it isn't already disabled by grace.
                if s.status != "disabled":
                    if not cfg.get("disabled_due_to_missing_in_code"):
                        cfg["disabled_due_to_missing_in_code"] = True
                        cfg["disabled_due_to_missing_prev_is_active"] = bool(s.is_active)
                        cfg["disabled_due_to_missing_prev_status"] = str(s.status or "waiting")
                        cfg["disabled_due_to_missing_at"] = now.isoformat()
                    s.is_active = False
                    s.status = "missing"
                s.config = cfg
            for s in hub_sources:
                await self._emit_source_event(s, "source.updated")

        await self.session.commit()
        return {
            "missing_spiders": missing_keys,
            "newly_missing_spiders": sorted(newly_missing),
            "disabled_spiders": disabled,
            "grace_minutes": grace_minutes,
            "ts": now.isoformat(),
        }

    async def get_missing_spiders_report(self, *, limit: int = 200) -> list[dict[str, Any]]:
        """
        Returns a list of spiders that are missing from the codebase
        (as last observed by the workers via sync-spiders).
        """
        limit = max(1, min(int(limit or 200), 1000))

        hubs = (
            await self.session.execute(
                select(ParsingHub).order_by(ParsingHub.site_key.asc()).limit(limit)
            )
        ).scalars().all()

        missing_keys = []
        hub_by_key: dict[str, ParsingHub] = {}
        for hub in hubs:
            if not hub.site_key:
                continue
            cfg = hub.config or {}
            if isinstance(cfg, dict) and cfg.get("missing_in_code"):
                missing_keys.append(hub.site_key)
                hub_by_key[hub.site_key] = hub

        if not missing_keys:
            return []

        # Aggregate sources stats for these site_keys.
        stmt = (
            select(
                ParsingSource.site_key,
                func.count(ParsingSource.id).label("sources_total"),
                func.sum(case((ParsingSource.is_active.is_(True), 1), else_=0)).label("sources_active"),
                func.sum(case((ParsingSource.status == "missing", 1), else_=0)).label("sources_missing"),
                func.sum(case((ParsingSource.status == "disabled", 1), else_=0)).label("sources_disabled"),
            )
            .where(ParsingSource.site_key.in_(missing_keys))
            .group_by(ParsingSource.site_key)
        )
        rows = (await self.session.execute(stmt)).all()
        stats_by_key = {
            str(r.site_key): {
                "sources_total": int(r.sources_total or 0),
                "sources_active": int(r.sources_active or 0),
                "sources_missing": int(r.sources_missing or 0),
                "sources_disabled": int(r.sources_disabled or 0),
            }
            for r in rows
            if r and r.site_key
        }

        report: list[dict[str, Any]] = []
        for key in sorted(missing_keys):
            hub = hub_by_key.get(key)
            cfg = dict(hub.config or {}) if hub else {}
            report.append(
                {
                    "site_key": key,
                    "hub_url": hub.url if hub else None,
                    "missing_since": cfg.get("missing_in_code_since"),
                    "last_seen_in_code_at": cfg.get("last_seen_in_code_at"),
                    "last_missing_seen_at": cfg.get("missing_in_code_last_seen_at"),
                    "stats": stats_by_key.get(key, {}),
                    "hub_config": cfg,
                }
            )
        return report

    async def set_source_active_status(self, source_id: int, is_active: bool) -> bool:
        source = (await self.session.execute(select(ParsingSource).where(ParsingSource.id == source_id))).scalar_one_or_none()
        if not source:
            return False
        source.is_active = is_active
        source.status = "waiting" if is_active else "disabled"
        await self._emit_source_event(source, "source.updated")
        await self.session.commit()
        return True


    async def set_source_status(self, source_id: int, status: str):
        source = (await self.session.execute(select(ParsingSource).where(ParsingSource.id == source_id))).scalar_one_or_none()
        if not source:
            return
        source.status = status
        await self._emit_source_event(source, "source.updated")
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
            await self._emit_source_event(source, "source.updated")
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
            await self._emit_source_event(source, "source.updated")
            await self.session.commit()

    async def update_source(self, source_id: int, data: dict) -> Optional[ParsingSource]:
        stmt = select(ParsingSource).where(ParsingSource.id == source_id)
        result = await self.session.execute(stmt)
        source = result.scalar_one_or_none()
        
        if source:
            for key, value in data.items():
                if hasattr(source, key):
                    setattr(source, key, value)
            await self._emit_source_event(source, "source.updated")
            await self.session.commit()
            await self.session.refresh(source)
            return source
        return None

    async def log_parsing_run(
        self,
        source_id: int,
        status: str,
        items_scraped: int,
        items_new: int,
        error_message: str | None = None,
    ) -> ParsingRun:
        run = ParsingRun(
            source_id=int(source_id),
            status=str(status),
            items_scraped=int(items_scraped or 0),
            items_new=int(items_new or 0),
            error_message=error_message,
        )
        self.session.add(run)
        await self.session.flush()
        await enqueue_outbox_event(self.session, aggregate_type="ops_run", aggregate_id=str(run.id), event_type="ops.run.created", payload={"id": run.id, "source_id": run.source_id, "status": run.status, "items_scraped": run.items_scraped, "items_new": run.items_new, "error_message": run.error_message, "duration_seconds": run.duration_seconds, "logs": run.logs, "created_at": run.created_at.isoformat() if run.created_at else None, "updated_at": run.updated_at.isoformat() if run.updated_at else None})
        await enqueue_outbox_event(self.session, aggregate_type="ops_run", aggregate_id=str(run.id), event_type="ops.run.updated", payload={"id": run.id, "source_id": run.source_id, "status": run.status, "items_scraped": run.items_scraped, "items_new": run.items_new, "error_message": run.error_message, "duration_seconds": run.duration_seconds, "logs": run.logs, "created_at": run.created_at.isoformat() if run.created_at else None, "updated_at": run.updated_at.isoformat() if run.updated_at else None})
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def create_parsing_run(
        self,
        *,
        source_id: int,
        status: str,
        items_scraped: int = 0,
        items_new: int = 0,
        error_message: str | None = None,
        duration_seconds: float | None = None,
        logs: str | None = None,
    ) -> ParsingRun:
        run = ParsingRun(
            source_id=int(source_id),
            status=str(status),
            items_scraped=int(items_scraped or 0),
            items_new=int(items_new or 0),
            error_message=error_message,
            duration_seconds=duration_seconds,
            logs=logs,
        )
        self.session.add(run)
        await self.session.flush()
        await enqueue_outbox_event(self.session, aggregate_type="ops_run", aggregate_id=str(run.id), event_type="ops.run.created", payload={"id": run.id, "source_id": run.source_id, "status": run.status, "items_scraped": run.items_scraped, "items_new": run.items_new, "error_message": run.error_message, "duration_seconds": run.duration_seconds, "logs": run.logs, "created_at": run.created_at.isoformat() if run.created_at else None, "updated_at": run.updated_at.isoformat() if run.updated_at else None})
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
    ) -> ParsingRun | None:
        stmt = select(ParsingRun).where(ParsingRun.id == int(run_id))
        run = (await self.session.execute(stmt)).scalar_one_or_none()
        if not run:
            return None

        if status is not None:
            run.status = str(status)
        if items_scraped is not None:
            run.items_scraped = int(items_scraped or 0)
        if items_new is not None:
            run.items_new = int(items_new or 0)
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
                "site_key": row.site_key,
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
            await self._emit_category_event(category, "category.updated")
            return category

        category = DiscoveredCategory(**data)
        self.session.add(category)
        await self.session.flush()
        await self._emit_category_event(category, "category.created")
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

        created = False
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
            created = True
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
        await self._emit_source_event(source, "source.created" if created else "source.updated")
        await self._emit_category_event(category, "category.updated")
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
