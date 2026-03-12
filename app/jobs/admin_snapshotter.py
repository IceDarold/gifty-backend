from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.analytics_events.emitters import emit_event
from app.config import get_settings
from app.db import get_redis, get_session_context
from app.repositories.catalog import PostgresCatalogRepository
from app.repositories.frontend_routing import FrontendRoutingRepository
from app.repositories.parsing import ParsingRepository
from app.repositories.telegram import TelegramRepository
from app.schemas.frontend import (
    FrontendAllowedHostDTO,
    FrontendAppDTO,
    FrontendAuditLogDTO,
    FrontendProfileDTO,
    FrontendReleaseDTO,
    FrontendRuleDTO,
    FrontendRuntimeStateDTO,
)
from app.schemas.parsing import DiscoveredCategorySchema, ParsingSourceSchema
from app.services.loki_logs import LokiLogsClient, build_logql_query
from routes import internal as internal_routes

logger = logging.getLogger("admin_snapshotter")


async def _emit_snapshot(channel: str, payload: Any) -> None:
    generated_at = datetime.now(timezone.utc).isoformat()
    await emit_event(
        event_type=f"admin.snapshot.{channel}",
        source="internal",
        metrics={"value": 1.0},
        payload={
            "data": payload,
            "generated_at": generated_at,
        },
    )
    await emit_event(
        event_type="admin.snapshot_meta",
        source="internal",
        metrics={"value": 1.0},
        payload={
            "channel": channel,
            "generated_at": generated_at,
        },
    )


def _serialize_models(items: List[Any], schema) -> List[dict]:
    out: List[dict] = []
    for item in items:
        try:
            out.append(schema.model_validate(item).model_dump())
        except Exception:
            continue
    return out


async def _snapshot_dashboard(db, redis) -> None:
    try:
        health = await internal_routes.get_system_health(db=db, redis=redis, _=None)
        await _emit_snapshot("dashboard.health", health)
    except Exception:
        logger.exception("dashboard.health snapshot failed")

    try:
        settings = get_settings()
        scraping = await analytics_routes.get_scraping_monitoring(settings=settings, db=db)
        await _emit_snapshot("dashboard.scraping", scraping)
    except Exception:
        logger.exception("dashboard.scraping snapshot failed")

    try:
        repo = ParsingRepository(db, redis=redis)
        sources = await repo.get_all_sources()
        items = _serialize_models(list(sources), ParsingSourceSchema)
        await _emit_snapshot("dashboard.sources", items)
        for src in sources:
            try:
                await _emit_snapshot(f"dashboard.source_detail:{int(src.id)}", ParsingSourceSchema.model_validate(src).model_dump())
                products = await internal_routes.get_source_products(
                    source_id=int(src.id),
                    limit=200,
                    offset=0,
                    db=db,
                    _=None,
                )
                await _emit_snapshot(f"dashboard.source_products:{int(src.id)}", products)
            except Exception:
                continue
    except Exception:
        logger.exception("dashboard.sources snapshot failed")

    try:
        backlog_raw = await internal_routes.get_discovery_backlog(limit=200, db=db, _=None)
        backlog_items = _serialize_models(list(backlog_raw), DiscoveredCategorySchema)
        await _emit_snapshot("dashboard.discovered_categories", backlog_items)
    except Exception:
        logger.exception("dashboard.discovered_categories snapshot failed")

    try:
        workers = await internal_routes.get_active_workers(db=db, redis=redis, _=None)
        await _emit_snapshot("dashboard.workers", workers)
    except Exception:
        logger.exception("dashboard.workers snapshot failed")

    try:
        queue = await internal_routes.get_queue_stats(_=None)
        queue["updated_at"] = datetime.now(timezone.utc).isoformat()
        await _emit_snapshot("dashboard.queue", queue)
    except Exception:
        logger.exception("dashboard.queue snapshot failed")


async def _snapshot_ops(db, redis) -> None:
    try:
        sites = await internal_routes.get_ops_sites(db=db, _=None)
        await _emit_snapshot("ops.sites", sites)
    except Exception:
        logger.exception("ops.sites snapshot failed")

    try:
        scheduler = await internal_routes.get_ops_scheduler_stats(db=db, redis=redis, force_fresh=False, _=None)
        await _emit_snapshot("ops.scheduler_stats", scheduler)
    except Exception:
        logger.exception("ops.scheduler_stats snapshot failed")

    try:
        discovery = await internal_routes.get_ops_discovery_categories(
            state="new,promoted,rejected,inactive",
            site_key=None,
            q=None,
            limit=200,
            offset=0,
            db=db,
            _=None,
        )
        await _emit_snapshot("ops.discovery", discovery)
    except Exception:
        logger.exception("ops.discovery snapshot failed")

    try:
        active = await internal_routes.get_ops_active_runs(limit=200, db=db, _=None)
        await _emit_snapshot("ops.runs.active", active)
    except Exception:
        logger.exception("ops.runs.active snapshot failed")

    try:
        queued = await internal_routes.get_ops_queued_runs(limit=200, offset=0, db=db, _=None)
        await _emit_snapshot("ops.runs.queued", queued)
    except Exception:
        logger.exception("ops.runs.queued snapshot failed")

    try:
        completed = await internal_routes.get_queue_history(limit=200, offset=0, status="completed", db=db, _=None)
        await _emit_snapshot("ops.runs.completed", completed)
    except Exception:
        logger.exception("ops.runs.completed snapshot failed")

    try:
        errors = await internal_routes.get_queue_history(limit=200, offset=0, status="error", db=db, _=None)
        await _emit_snapshot("ops.runs.error", errors)
    except Exception:
        logger.exception("ops.runs.error snapshot failed")

    try:
        pipeline_map: Dict[str, Any] = {}
        repo = ParsingRepository(db, redis=redis)
        sources = await repo.get_all_sources()
        site_keys = sorted({s.site_key for s in sources if getattr(s, "site_key", None)})
        for key in site_keys:
            try:
                pipeline_map[key] = await internal_routes.get_ops_site_pipeline(site_key=key, lane_limit=120, lane_offset=0, db=db, _=None)
            except Exception:
                continue
        await _emit_snapshot("ops.pipeline", pipeline_map)
    except Exception:
        logger.exception("ops.pipeline snapshot failed")

    try:
        run_details: Dict[str, Any] = {}
        active = await internal_routes.get_ops_active_runs(limit=200, db=db, _=None)
        queued = await internal_routes.get_ops_queued_runs(limit=200, offset=0, db=db, _=None)
        run_ids: List[int] = []
        for payload in (active, queued):
            items = payload.get("items") if isinstance(payload, dict) else []
            for it in items or []:
                rid = it.get("run_id")
                if isinstance(rid, int):
                    run_ids.append(rid)
        for rid in run_ids:
            try:
                detail = await internal_routes.get_ops_run_details(run_id=rid, db=db, _=None)
                run_details[str(rid)] = detail
            except Exception:
                continue
        await _emit_snapshot("ops.run_details", run_details)
    except Exception:
        logger.exception("ops.run_details snapshot failed")

    try:
        source_trends: Dict[str, Any] = {}
        repo = ParsingRepository(db, redis=redis)
        sources = await repo.get_all_sources()
        for src in sources:
            sid = int(src.id)
            per_gran: Dict[str, Any] = {}
            for granularity, buckets in (("week", 12), ("day", 30), ("hour", 72), ("minute", 180)):
                try:
                    trend = await internal_routes.get_ops_source_items_trend(
                        source_id=sid,
                        granularity=granularity,
                        buckets=buckets,
                        days=None,
                        db=db,
                        _=None,
                    )
                    per_gran[granularity] = trend
                except Exception:
                    continue
            if per_gran:
                source_trends[str(sid)] = per_gran
        await _emit_snapshot("ops.source_items_trend", source_trends)
    except Exception:
        logger.exception("ops.source_items_trend snapshot failed")


async def _snapshot_catalog(db) -> None:
    try:
        repo = PostgresCatalogRepository(db)
        items: List[dict] = []
        offset = 0
        limit = 500
        while True:
            batch = await repo.get_products(limit=limit, offset=offset)
            if not batch:
                break
            payload = await internal_routes.get_products_endpoint(limit=limit, offset=offset, db=db, _=None)
            batch_items = payload.get("items", [])
            items.extend(batch_items)
            if len(batch_items) < limit:
                break
            offset += limit
        await _emit_snapshot("catalog.products", items)
    except Exception:
        logger.exception("catalog.products snapshot failed")


async def _snapshot_settings(db) -> None:
    try:
        runtime = await internal_routes.get_ops_runtime_settings(db=db, _=None)
        await _emit_snapshot("settings.runtime", runtime)
    except Exception:
        logger.exception("settings.runtime snapshot failed")

    try:
        merchants = await internal_routes.list_merchants(limit=500, offset=0, q=None, db=db, _=None)
        await _emit_snapshot("settings.merchants", merchants)
    except Exception:
        logger.exception("settings.merchants snapshot failed")

    try:
        repo = TelegramRepository(db)
        subscribers = await repo.get_all_subscribers()
        items = []
        for sub in subscribers:
            items.append(
                {
                    "chat_id": sub.chat_id,
                    "name": sub.name,
                    "role": sub.role,
                    "permissions": sub.permissions,
                    "subscriptions": sub.subscriptions,
                    "language": sub.language,
                    "is_active": sub.is_active,
                    "created_at": sub.created_at.isoformat() if sub.created_at else None,
                    "updated_at": sub.updated_at.isoformat() if sub.updated_at else None,
                }
            )
        await _emit_snapshot("settings.subscribers", items)
    except Exception:
        logger.exception("settings.subscribers snapshot failed")


async def _snapshot_frontend(db) -> None:
    try:
        repo = FrontendRoutingRepository(db)
        apps = _serialize_models(await repo.list_apps(), FrontendAppDTO)
        await _emit_snapshot("frontend.apps", apps)
        releases = _serialize_models(await repo.list_releases(), FrontendReleaseDTO)
        await _emit_snapshot("frontend.releases", releases)
        profiles = _serialize_models(await repo.list_profiles(), FrontendProfileDTO)
        await _emit_snapshot("frontend.profiles", profiles)
        rules = _serialize_models(await repo.list_rules(), FrontendRuleDTO)
        await _emit_snapshot("frontend.rules", rules)
        runtime_state = await repo.get_runtime_state()
        if runtime_state is not None:
            await _emit_snapshot("frontend.runtime_state", FrontendRuntimeStateDTO.model_validate(runtime_state).model_dump())
        allowed_hosts = _serialize_models(await repo.list_allowed_hosts(), FrontendAllowedHostDTO)
        await _emit_snapshot("frontend.allowed_hosts", allowed_hosts)
        audit = _serialize_models(await repo.list_audit_log(), FrontendAuditLogDTO)
        await _emit_snapshot("frontend.audit_log", audit)
    except Exception:
        logger.exception("frontend snapshots failed")


async def _snapshot_logs() -> None:
    try:
        client = LokiLogsClient()
        now_ns = int(datetime.now(timezone.utc).timestamp() * 1_000_000_000)
        lines = await client.query_range(
            query=build_logql_query(),
            start_ns=now_ns - 5 * 60 * 1_000_000_000,
            end_ns=now_ns,
            limit=200,
            direction="BACKWARD",
        )
        items = [
            {
                "ts": line.ts_iso,
                "service": line.labels.get("service") or line.labels.get("job"),
                "level": line.labels.get("level") or line.labels.get("severity"),
                "message": line.line,
            }
            for line in lines
        ]
        await _emit_snapshot("logs.snapshot", {"items": items})
        services = await client.label_values("service")
        await _emit_snapshot("logs.services", {"items": [{"service": s} for s in services]})
    except Exception:
        logger.exception("logs snapshot failed")


async def run_admin_snapshotter_tick() -> None:
    redis = await get_redis()
    async with get_session_context() as db:
        await _snapshot_dashboard(db, redis)
        await _snapshot_ops(db, redis)
        await _snapshot_catalog(db)
        await _snapshot_settings(db)
        await _snapshot_frontend(db)
    await _snapshot_logs()


async def run_admin_snapshotter_loop(interval_seconds: float) -> None:
    logger.info("Admin snapshotter started interval=%ss", interval_seconds)
    while True:
        try:
            await run_admin_snapshotter_tick()
        except Exception:
            logger.exception("admin snapshotter tick failed")
        await asyncio.sleep(max(1.0, interval_seconds))


async def run_admin_snapshotter_loop_split() -> None:
    settings = get_settings()
    dashboard_interval = max(1.0, float(settings.admin_snapshot_dashboard_seconds or 30))
    ops_interval = max(1.0, float(settings.admin_snapshot_ops_seconds or 30))
    catalog_interval = max(1.0, float(settings.admin_snapshot_catalog_seconds or 60))
    settings_interval = max(1.0, float(settings.admin_snapshot_settings_seconds or 60))
    frontend_interval = max(1.0, float(settings.admin_snapshot_frontend_seconds or 60))
    logs_interval = max(1.0, float(settings.admin_snapshot_logs_seconds or 15))

    last = {
        "dashboard": 0.0,
        "ops": 0.0,
        "catalog": 0.0,
        "settings": 0.0,
        "frontend": 0.0,
        "logs": 0.0,
    }

    logger.info(
        "Admin snapshotter split loop dashboard=%ss ops=%ss catalog=%ss settings=%ss frontend=%ss logs=%ss",
        dashboard_interval,
        ops_interval,
        catalog_interval,
        settings_interval,
        frontend_interval,
        logs_interval,
    )

    while True:
        now = asyncio.get_event_loop().time()
        try:
            redis = await get_redis()
            async with get_session_context() as db:
                if now - last["dashboard"] >= dashboard_interval:
                    await _snapshot_dashboard(db, redis)
                    last["dashboard"] = now
                if now - last["ops"] >= ops_interval:
                    await _snapshot_ops(db, redis)
                    last["ops"] = now
                if now - last["catalog"] >= catalog_interval:
                    await _snapshot_catalog(db)
                    last["catalog"] = now
                if now - last["settings"] >= settings_interval:
                    await _snapshot_settings(db)
                    last["settings"] = now
                if now - last["frontend"] >= frontend_interval:
                    await _snapshot_frontend(db)
                    last["frontend"] = now
            if now - last["logs"] >= logs_interval:
                await _snapshot_logs()
                last["logs"] = now
        except Exception:
            logger.exception("admin snapshotter tick failed")
        await asyncio.sleep(0.5)
