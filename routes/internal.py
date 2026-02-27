from fastapi import APIRouter, Depends, HTTPException, Header, Query, Body
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from typing import List, Optional, AsyncGenerator, Any
from datetime import datetime, timezone, timedelta
import json
import asyncio
import re
import hashlib
import logging
from pydantic import BaseModel, Field
from prometheus_client import Counter, Histogram, REGISTRY

from app.db import get_db, get_redis
from app.repositories.catalog import PostgresCatalogRepository
from app.config import get_settings

from app.config import get_settings
from app.utils.telegram_auth import verify_telegram_init_data
from app.repositories.parsing import ParsingRepository
from app.repositories.telegram import TelegramRepository
from app.models import ParsingSource, ParsingRun, DiscoveredCategory, ParsingHub, Product, OpsRuntimeState
from app.models import ProductCategoryLink
from app.services.loki_logs import LokiLogsClient, build_logql_query

router = APIRouter(prefix="/api/v1/internal", tags=["internal"])
settings = get_settings()
_queue_reconcile_lock = asyncio.Lock()
_last_queue_reconcile_at: Optional[datetime] = None
OPS_EVENTS_CHANNEL = "ops:events"
OPS_TASK_SNAPSHOTS_KEY = "ops:tasks:snapshots"
OPS_TASK_SNAPSHOTS_MAX = 20000
OPS_SCHEDULER_PAUSE_KEY = "ops:scheduler:paused"
OPS_SNAPSHOT_META_KEY = "ops:snapshot:meta:v1"
OPS_SNAPSHOT_OVERVIEW_KEY = "ops:snapshot:overview:v1"
OPS_SNAPSHOT_SCHEDULER_STATS_KEY = "ops:snapshot:scheduler_stats:v1"
OPS_SNAPSHOT_ITEMS_TREND_KEY = "ops:snapshot:items_trend:{granularity}:{buckets}:v1"
OPS_SNAPSHOT_TASKS_TREND_KEY = "ops:snapshot:tasks_trend:{granularity}:{buckets}:v1"
_TG_ADMIN_AUTH_CACHE_TTL_SEC = 60
_tg_admin_auth_cache: dict[int, datetime] = {}
_tg_admin_auth_cache_lock = asyncio.Lock()

OPS_INTERVAL_MIN_MS = 1000
OPS_INTERVAL_MAX_MS = 600000
OPS_AGGREGATOR_INTERVAL_MIN_MS = 500
OPS_AGGREGATOR_INTERVAL_MAX_MS = 60000
OPS_SNAPSHOT_TTL_MIN_MS = 1000
OPS_SNAPSHOT_TTL_MAX_MS = 300000
OPS_STALE_MAX_AGE_MIN_MS = 5000
OPS_STALE_MAX_AGE_MAX_MS = 600000

OPS_CLIENT_INTERVAL_DEFAULTS: dict[str, int] = {
    "ops.overview_ms": 30000,
    "ops.sites_ms": 30000,
    "ops.pipeline_ms": 30000,
    "ops.active_runs_ms": 30000,
    "ops.discovery_ms": 30000,
    "ops.run_details_ms": 15000,
    "ops.queue_lanes_ms": 30000,
    "ops.scheduler_stats_ms": 30000,
    "ops.items_trend_ms": 30000,
    "ops.tasks_trend_ms": 30000,
    "ops.source_trend_ms": 30000,
    "dashboard.stats_ms": 60000,
    "dashboard.health_ms": 30000,
    "dashboard.scraping_ms": 60000,
    "dashboard.sources_ms": 30000,
    "dashboard.workers_ms": 30000,
    "dashboard.queue_stats_ms": 5000,
    "dashboard.queue_tasks_ms": 10000,
    "dashboard.queue_history_ms": 15000,
    "intelligence.summary_ms": 300000,
    "catalog.revalidate_ms": 30000,
}

def _get_or_create_collector(name: str, factory):
    # During tests the module can be imported in multiple ways (app.main imports routes.internal,
    # and some tests import routes.internal directly). Avoid duplicate registration errors by reusing
    # existing collectors in the default REGISTRY.
    existing = getattr(REGISTRY, "_names_to_collectors", {}).get(name)  # type: ignore[attr-defined]
    if existing is not None:
        return existing
    return factory()


ops_aggregator_runs_total = _get_or_create_collector(
    "ops_aggregator_runs_total",
    lambda: Counter("ops_aggregator_runs_total", "Total ops aggregator runs"),
)
ops_aggregator_run_duration_ms = _get_or_create_collector(
    "ops_aggregator_run_duration_ms",
    lambda: Histogram("ops_aggregator_run_duration_ms", "Duration of ops aggregator run in milliseconds"),
)
ops_snapshot_cache_hits_total = _get_or_create_collector(
    "ops_snapshot_cache_hits_total",
    lambda: Counter("ops_snapshot_cache_hits_total", "Ops snapshot cache hits"),
)
ops_snapshot_cache_misses_total = _get_or_create_collector(
    "ops_snapshot_cache_misses_total",
    lambda: Counter("ops_snapshot_cache_misses_total", "Ops snapshot cache misses"),
)
ops_snapshot_stale_served_total = _get_or_create_collector(
    "ops_snapshot_stale_served_total",
    lambda: Counter("ops_snapshot_stale_served_total", "Ops stale snapshots served"),
)
ops_snapshot_refresh_errors_total = _get_or_create_collector(
    "ops_snapshot_refresh_errors_total",
    lambda: Counter("ops_snapshot_refresh_errors_total", "Ops snapshot refresh errors"),
)
ops_settings_updates_total = _get_or_create_collector(
    "ops_settings_updates_total",
    lambda: Counter("ops_settings_updates_total", "Ops runtime settings updates"),
)
logger = logging.getLogger("ops_runtime")
OPS_SNAPSHOT_REFRESH_LOCK_PREFIX = "ops:snapshot:refresh_lock:"
OPS_SETTINGS_UPDATE_RATE_LIMIT_MS = 1000


class OpsRuntimeSettingsUpdateRequest(BaseModel):
    ops_aggregator_enabled: Optional[bool] = None
    ops_aggregator_interval_ms: Optional[int] = Field(default=None, ge=OPS_AGGREGATOR_INTERVAL_MIN_MS, le=OPS_AGGREGATOR_INTERVAL_MAX_MS)
    ops_snapshot_ttl_ms: Optional[int] = Field(default=None, ge=OPS_SNAPSHOT_TTL_MIN_MS, le=OPS_SNAPSHOT_TTL_MAX_MS)
    ops_stale_max_age_ms: Optional[int] = Field(default=None, ge=OPS_STALE_MAX_AGE_MIN_MS, le=OPS_STALE_MAX_AGE_MAX_MS)
    ops_client_intervals: Optional[dict[str, int]] = None


def _normalize_client_intervals(raw: Optional[dict[str, Any]]) -> dict[str, int]:
    normalized = dict(OPS_CLIENT_INTERVAL_DEFAULTS)
    if not isinstance(raw, dict):
        return normalized
    for key, value in raw.items():
        if key not in OPS_CLIENT_INTERVAL_DEFAULTS:
            continue
        try:
            num = int(value)
        except Exception:
            continue
        if OPS_INTERVAL_MIN_MS <= num <= OPS_INTERVAL_MAX_MS:
            normalized[key] = num
    return normalized


def _extract_site_name_from_config(cfg: Optional[dict]) -> Optional[str]:
    if not isinstance(cfg, dict):
        return None
    for key in ("discovery_name", "site_name", "name", "display_name", "site_title", "title"):
        value = cfg.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


async def _sync_hub_from_hub_source(db: AsyncSession, source: ParsingSource) -> None:
    """
    Keep parsing_hubs in sync when hub runtime source is edited/reported.
    Discovery flow should rely on parsing_hubs as source of truth.
    """
    if source.type != "hub":
        return

    from sqlalchemy import select

    hub = (
        await db.execute(
            select(ParsingHub).where(ParsingHub.site_key == source.site_key)
        )
    ).scalar_one_or_none()
    if not hub:
        return

    source_cfg = source.config or {}
    site_name = _extract_site_name_from_config(source_cfg)

    hub.url = source.url
    hub.status = source.status or hub.status
    hub.is_active = bool(source.is_active)
    hub.refresh_interval_hours = source.refresh_interval_hours or hub.refresh_interval_hours
    if source.strategy:
        hub.strategy = source.strategy
    if site_name:
        hub.name = site_name


async def _get_scheduler_paused_state(db: AsyncSession) -> bool:
    from sqlalchemy import select

    value = (
        await db.execute(
            select(OpsRuntimeState.scheduler_paused).where(OpsRuntimeState.id == 1)
        )
    ).scalar_one_or_none()
    return bool(value) if value is not None else False


async def _set_scheduler_paused_state(db: AsyncSession, paused: bool) -> None:
    row = await db.get(OpsRuntimeState, 1)
    if row is None:
        db.add(OpsRuntimeState(id=1, scheduler_paused=paused))
    else:
        row.scheduler_paused = paused
    await db.commit()


def _runtime_settings_bounds() -> dict[str, dict[str, int]]:
    return {
        "ops_aggregator_interval_ms": {"min": OPS_AGGREGATOR_INTERVAL_MIN_MS, "max": OPS_AGGREGATOR_INTERVAL_MAX_MS},
        "ops_snapshot_ttl_ms": {"min": OPS_SNAPSHOT_TTL_MIN_MS, "max": OPS_SNAPSHOT_TTL_MAX_MS},
        "ops_stale_max_age_ms": {"min": OPS_STALE_MAX_AGE_MIN_MS, "max": OPS_STALE_MAX_AGE_MAX_MS},
        "ops_client_intervals": {"min": OPS_INTERVAL_MIN_MS, "max": OPS_INTERVAL_MAX_MS},
    }


async def _get_or_create_ops_runtime_state(db: AsyncSession) -> OpsRuntimeState:
    state = await db.get(OpsRuntimeState, 1)
    if state is None:
        state = OpsRuntimeState(
            id=1,
            scheduler_paused=False,
            settings_version=1,
            ops_aggregator_enabled=True,
            ops_aggregator_interval_ms=2000,
            ops_snapshot_ttl_ms=10000,
            ops_stale_max_age_ms=60000,
            ops_client_intervals=dict(OPS_CLIENT_INTERVAL_DEFAULTS),
        )
        db.add(state)
        await db.commit()
        await db.refresh(state)
    else:
        normalized = _normalize_client_intervals(state.ops_client_intervals if isinstance(state.ops_client_intervals, dict) else None)
        if state.ops_client_intervals != normalized:
            state.ops_client_intervals = normalized
            await db.commit()
            await db.refresh(state)
    return state


def _serialize_ops_runtime_settings(state: OpsRuntimeState) -> dict[str, Any]:
    return {
        "status": "ok",
        "item": {
            "scheduler_paused": bool(state.scheduler_paused),
            "settings_version": int(state.settings_version or 1),
            "ops_aggregator_enabled": bool(state.ops_aggregator_enabled),
            "ops_aggregator_interval_ms": int(state.ops_aggregator_interval_ms or 2000),
            "ops_snapshot_ttl_ms": int(state.ops_snapshot_ttl_ms or 10000),
            "ops_stale_max_age_ms": int(state.ops_stale_max_age_ms or 60000),
            "ops_client_intervals": _normalize_client_intervals(state.ops_client_intervals if isinstance(state.ops_client_intervals, dict) else None),
            "defaults": dict(OPS_CLIENT_INTERVAL_DEFAULTS),
            "bounds": _runtime_settings_bounds(),
            "updated_by": state.updated_by,
            "updated_at": _iso(state.updated_at),
        },
    }


def _ops_actor_id_from_principal(principal: str) -> Optional[int]:
    if principal.startswith("tg_admin:"):
        try:
            return int(principal.split(":", 1)[1])
        except Exception:
            return None
    return None


def _snapshot_key(block: str, *, granularity: Optional[str] = None, buckets: Optional[int] = None) -> str:
    if block == "overview":
        return OPS_SNAPSHOT_OVERVIEW_KEY
    if block == "scheduler_stats":
        return OPS_SNAPSHOT_SCHEDULER_STATS_KEY
    if block == "items_trend":
        return OPS_SNAPSHOT_ITEMS_TREND_KEY.format(granularity=granularity or "day", buckets=int(buckets or 30))
    if block == "tasks_trend":
        return OPS_SNAPSHOT_TASKS_TREND_KEY.format(granularity=granularity or "day", buckets=int(buckets or 30))
    raise ValueError(f"Unknown snapshot block: {block}")


async def _snapshot_meta_get(redis: Redis) -> dict[str, Any]:
    try:
        raw = await redis.get(OPS_SNAPSHOT_META_KEY)
        if not raw:
            return {}
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


async def _snapshot_meta_set(redis: Redis, meta: dict[str, Any], ttl_ms: int) -> None:
    await redis.set(OPS_SNAPSHOT_META_KEY, json.dumps(meta, ensure_ascii=False), ex=max(1, int(ttl_ms / 1000)))


async def _snapshot_read(redis: Redis, key: str) -> Optional[dict[str, Any]]:
    try:
        raw = await redis.get(key)
        if not raw:
            return None
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


async def _snapshot_write(
    redis: Redis,
    *,
    block: str,
    key: str,
    payload: dict[str, Any],
    ttl_ms: int,
) -> tuple[dict[str, Any], bool]:
    generated_at = datetime.now(timezone.utc).isoformat()
    wrapped = {
        "block": block,
        "key": key,
        "generated_at": generated_at,
        "payload": payload,
    }
    body = json.dumps(wrapped, ensure_ascii=False)
    meta = await _snapshot_meta_get(redis)
    prev_hash = str(meta.get(key, {}).get("hash", ""))
    curr_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    changed = prev_hash != curr_hash
    await redis.set(key, body, ex=max(1, int(ttl_ms / 1000)))
    next_version = int(meta.get(key, {}).get("version", 0)) + (1 if changed else 0)
    meta[key] = {
        "block": block,
        "hash": curr_hash,
        "version": next_version,
        "generated_at": generated_at,
    }
    await _snapshot_meta_set(redis, meta, ttl_ms=ttl_ms)
    return wrapped, changed


def _add_snapshot_meta_fields(
    payload: dict[str, Any],
    *,
    cache_key: str,
    generated_at: Optional[str],
    stale: bool,
) -> dict[str, Any]:
    out = dict(payload)
    out["snapshot_key"] = cache_key
    out["generated_at"] = generated_at or out.get("generated_at")
    out["stale"] = bool(stale)
    return out


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _parse_iso_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _is_snapshot_stale(generated_at: Optional[str], stale_max_age_ms: int) -> bool:
    generated = _parse_iso_dt(generated_at)
    if generated is None:
        return True
    now_utc = datetime.now(timezone.utc)
    return (now_utc - generated).total_seconds() * 1000 > int(stale_max_age_ms)


def _snapshot_refresh_lock_key(cache_key: str) -> str:
    digest = hashlib.sha1(cache_key.encode("utf-8")).hexdigest()  # nosec B324
    return f"{OPS_SNAPSHOT_REFRESH_LOCK_PREFIX}{digest}"


async def _trigger_snapshot_refresh_if_needed(
    *,
    redis: Optional[Redis],
    cache_key: str,
    block: str,
    ttl_ms: int,
    compute_fn: Any,
) -> None:
    if redis is None:
        return
    lock_key = _snapshot_refresh_lock_key(cache_key)
    try:
        acquired = await redis.set(lock_key, "1", nx=True, ex=max(2, int(ttl_ms / 1000)))
    except Exception:
        logger.warning("ops snapshot refresh lock failed for %s", cache_key)
        return
    if not acquired:
        return

    async def _runner() -> None:
        try:
            payload = await compute_fn()
            wrapped, changed = await _snapshot_write(
                redis,
                block=block,
                key=cache_key,
                payload=payload,
                ttl_ms=ttl_ms,
            )
            if changed:
                meta = await _snapshot_meta_get(redis)
                await _publish_ops_event(
                    redis,
                    "ops.snapshot.updated",
                    {
                        "block": block,
                        "key": cache_key,
                        "version": meta.get(cache_key, {}).get("version", 0),
                        "generated_at": wrapped.get("generated_at"),
                    },
                )
        except Exception:
            ops_snapshot_refresh_errors_total.inc()
            logger.warning("ops snapshot background refresh failed for %s", cache_key)
        finally:
            try:
                await redis.delete(lock_key)
            except Exception:
                pass

    asyncio.create_task(_runner())


_CATEGORIES_INGESTED_RE = re.compile(r"Batch ingested:\s*\d+\s+products,\s*(\d+)\s+categories", re.IGNORECASE)
_RUN_ERROR_MARKERS = ("failed to ingest batch",)


def _extract_categories_scraped_from_logs(logs: Optional[str]) -> int:
    if not logs:
        return 0
    total = 0
    for match in _CATEGORIES_INGESTED_RE.findall(logs):
        try:
            total += int(match)
        except Exception:
            continue
    return total


def _detect_run_error_from_logs(logs: Optional[str]) -> Optional[str]:
    if not logs:
        return None
    lower = logs.lower()
    for marker in _RUN_ERROR_MARKERS:
        if marker in lower:
            if marker == "failed to ingest batch":
                return "Failed to ingest batch"
            return f"Runtime log error marker detected: {marker}"
    return None


async def _fetch_rabbit_queue_stats() -> dict:
    import httpx
    import os

    rabbit_url = os.getenv("RABBITMQ_MANAGEMENT_URL", "http://guest:guest@rabbitmq:15672/api/queues/%2f/parsing_tasks")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(rabbit_url)
            if resp.status_code != 200:
                return {"status": "error", "message": f"RabbitMQ API returned {resp.status_code}"}
            data = resp.json()
            return {
                "queue_name": data.get("name"),
                "messages_ready": data.get("messages_ready", 0),
                "messages_unacknowledged": data.get("messages_unacknowledged", 0),
                "messages_total": data.get("messages", 0),
                "consumers": data.get("consumers", 0),
                "rate_publish": data.get("messages_details", {}).get("rate", 0),
                "status": "ok",
            }
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def _fetch_rabbit_queued_tasks(limit: int = 1000) -> list[dict]:
    """Peek queued Rabbit messages and return decoded task payloads."""
    import httpx
    import os

    rabbit_url = os.getenv("RABBITMQ_MANAGEMENT_URL", "http://guest:guest@rabbitmq:15672/api/queues/%2f/parsing_tasks")
    rabbit_get_url = rabbit_url.rstrip("/") + "/get"
    payload = {
        "count": max(1, min(limit, 2000)),
        "ackmode": "ack_requeue_true",
        "encoding": "auto",
        "truncate": 50000,
    }

    tasks: list[dict] = []
    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.post(rabbit_get_url, json=payload)
        resp.raise_for_status()
        raw = resp.json()
        raw_items = raw if isinstance(raw, list) else []
        for msg in raw_items:
            task = msg.get("payload")
            if isinstance(task, str):
                try:
                    task = json.loads(task)
                except Exception:
                    task = {}
            if not isinstance(task, dict):
                continue
            tasks.append(task)
    return tasks


async def _append_ops_task_snapshot(
    redis: Redis,
    *,
    ts: datetime,
    queue_total: int,
    running_total: int,
    completed_total: int,
    error_total: int,
) -> None:
    payload = {
        "ts": ts.isoformat(),
        "queue": int(queue_total or 0),
        "running": int(running_total or 0),
        "completed_total": int(completed_total or 0),
        "error_total": int(error_total or 0),
    }
    try:
        await redis.lpush(OPS_TASK_SNAPSHOTS_KEY, json.dumps(payload))
        await redis.ltrim(OPS_TASK_SNAPSHOTS_KEY, 0, OPS_TASK_SNAPSHOTS_MAX - 1)
    except Exception:
        # Non-critical telemetry path.
        return


async def _fetch_rabbit_queued_task_ids(limit: int = 1000) -> tuple[set[int], set[int]]:
    tasks = await _fetch_rabbit_queued_tasks(limit=limit)
    run_ids: set[int] = set()
    source_ids: set[int] = set()
    for task in tasks:
        run_id = task.get("run_id")
        source_id = task.get("source_id")
        if isinstance(run_id, int):
            run_ids.add(run_id)
        if isinstance(source_id, int):
            source_ids.add(source_id)
    return run_ids, source_ids


async def _publish_ops_event(redis: Optional[Redis], event_type: str, payload: dict) -> None:
    if redis is None:
        return
    try:
        await redis.publish(
            OPS_EVENTS_CHANNEL,
            json.dumps(
                {
                    "type": event_type,
                    "payload": payload,
                },
                ensure_ascii=False,
            ),
        )
    except Exception:
        # Non-critical: SSE can still recover via periodic REST refresh on client.
        pass


async def _reconcile_queued_runs_with_rabbit(
    db: AsyncSession,
    *,
    grace_seconds: int = 90,
    max_probe_messages: int = 1000,
) -> dict:
    """
    Reconcile DB queued runs with Rabbit queue.
    Marks stale queued runs as error when they are not present in Rabbit queue.
    """
    from sqlalchemy import select, update, func

    queue = await _fetch_rabbit_queue_stats()
    if queue.get("status") != "ok":
        return {"status": "skipped", "reason": "queue_unavailable"}

    now_utc = datetime.now(timezone.utc)
    stale_before = now_utc - timedelta(seconds=max(10, grace_seconds))

    queued_rows = (
        await db.execute(
            select(ParsingRun.id, ParsingRun.source_id, ParsingRun.created_at)
            .where(
                ParsingRun.status == "queued",
                ParsingRun.created_at < stale_before,
            )
        )
    ).all()
    if not queued_rows:
        return {"status": "ok", "stale_runs": 0, "source_status_fixed": 0}

    queued_run_ids = {int(row[0]) for row in queued_rows}
    queued_source_ids = {int(row[1]) for row in queued_rows}

    queue_total = int(queue.get("messages_total", 0) or 0)
    if queue_total <= 0:
        stale_run_ids = queued_run_ids
    else:
        if queue_total > max_probe_messages:
            return {"status": "skipped", "reason": "queue_too_large_to_probe", "queue_total": queue_total}
        try:
            rabbit_run_ids, _ = await _fetch_rabbit_queued_task_ids(limit=max_probe_messages)
        except Exception:
            return {"status": "skipped", "reason": "queue_probe_failed"}
        stale_run_ids = queued_run_ids - rabbit_run_ids

    if not stale_run_ids:
        return {"status": "ok", "stale_runs": 0, "source_status_fixed": 0}

    await db.execute(
        update(ParsingRun)
        .where(ParsingRun.id.in_(stale_run_ids), ParsingRun.status == "queued")
        .values(
            status="error",
            error_message="Queue reconciliation: task missing in RabbitMQ",
            updated_at=func.now(),
        )
    )

    affected_source_ids = {source_id for run_id, source_id, _ in queued_rows if int(run_id) in stale_run_ids}
    source_status_fixed = 0
    if affected_source_ids:
        active_source_rows = (
            await db.execute(
                select(ParsingRun.source_id)
                .where(
                    ParsingRun.source_id.in_(affected_source_ids),
                    ParsingRun.status.in_(("queued", "running")),
                )
                .distinct()
            )
        ).all()
        sources_with_active_runs = {int(row[0]) for row in active_source_rows}
        idle_sources = affected_source_ids - sources_with_active_runs
        if idle_sources:
            result = await db.execute(
                update(ParsingSource)
                .where(
                    ParsingSource.id.in_(idle_sources),
                    ParsingSource.status == "queued",
                )
                .values(status="waiting", updated_at=func.now())
            )
            source_status_fixed = int(result.rowcount or 0)

    await db.commit()
    return {
        "status": "ok",
        "stale_runs": len(stale_run_ids),
        "source_status_fixed": source_status_fixed,
        "checked_queued_runs": len(queued_run_ids),
        "queue_total": queue_total,
    }


async def _maybe_reconcile_queued_runs_with_rabbit(
    db: AsyncSession,
    *,
    cooldown_seconds: int = 12,
) -> dict:
    global _last_queue_reconcile_at

    now = datetime.now(timezone.utc)
    if _last_queue_reconcile_at and (now - _last_queue_reconcile_at).total_seconds() < max(1, cooldown_seconds):
        return {"status": "skipped", "reason": "cooldown"}

    async with _queue_reconcile_lock:
        now = datetime.now(timezone.utc)
        if _last_queue_reconcile_at and (now - _last_queue_reconcile_at).total_seconds() < max(1, cooldown_seconds):
            return {"status": "skipped", "reason": "cooldown"}
        result = await _reconcile_queued_runs_with_rabbit(db)
        _last_queue_reconcile_at = now
        return result

async def verify_internal_token(
    x_internal_token: Optional[str] = Header(None),
    x_tg_init_data: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
):
    # 1. Direct system token check
    expected_token = getattr(settings, "internal_api_token", "default_secret_token")
    if x_internal_token:
        print(f"DEBUG_AUTH: Received token starts with {x_internal_token[:4]}, Expected starts with {expected_token[:4]}")
        if x_internal_token == expected_token:
            return x_internal_token
        else:
            print(f"DEBUG_AUTH: TOKEN MISMATCH!")
        
    # 2. Telegram WebApp session check
    if x_tg_init_data:
        # Dev bypass
        if settings.env == "dev" and x_tg_init_data == "dev_user_1821014162":
            user_id = 1821014162
        else:
            if not verify_telegram_init_data(x_tg_init_data, settings.telegram_bot_token):
                raise HTTPException(status_code=403, detail="Invalid Telegram data")
                
            from urllib.parse import parse_qsl
            import json
            params = dict(parse_qsl(x_tg_init_data))
            user_data = json.loads(params.get("user", "{}"))
            user_id = int(user_data.get("id", 0))

        if user_id:
            now = datetime.now(timezone.utc)
            cached_until = _tg_admin_auth_cache.get(user_id)
            if cached_until and cached_until > now:
                return f"tg_admin:{user_id}"

            repo = TelegramRepository(db)
            subscriber = await repo.get_subscriber(user_id)
            if subscriber and subscriber.role in ["admin", "superadmin"]:
                async with _tg_admin_auth_cache_lock:
                    _tg_admin_auth_cache[user_id] = now + timedelta(seconds=_TG_ADMIN_AUTH_CACHE_TTL_SEC)
                return f"tg_admin:{user_id}"

    raise HTTPException(status_code=403, detail="Invalid internal token or unauthorized Telegram session")

@router.get("/scoring/tasks", summary="(Deprecated) Получить товары для скоринга")
async def get_scoring_tasks(_=Depends(verify_internal_token)):
    raise HTTPException(status_code=410, detail="Scoring is disabled")


@router.post("/scoring/submit", summary="(Deprecated) Сохранить результаты скоринга")
async def submit_scoring_results(_=Depends(verify_internal_token)):
    raise HTTPException(status_code=410, detail="Scoring is disabled")

from app.schemas.parsing import IngestBatchRequest, ParsingSourceSchema, ParsingSourceCreate, DiscoveredCategorySchema
from app.services.ingestion import IngestionService

@router.get("/monitoring", summary="Агрегированный мониторинг по сайтам")
async def get_sites_monitoring(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db, redis=redis)
    return await repo.get_sites_monitoring()

@router.get("/stats", summary="Статистика парсинга за 24ч")
async def get_parsing_stats(
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db)
    return await repo.get_24h_stats()

@router.get("/sources", response_model=List[ParsingSourceSchema], summary="Получить список источников парсинга")
async def get_parsing_sources(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db, redis=redis)
    sources = await repo.get_all_sources()
    # Still keep full list for now, but in future this should be paginated
    return sources

@router.post("/sources", response_model=ParsingSourceSchema, summary="Создать или обновить источник парсинга")
async def upsert_parsing_source(
    data: ParsingSourceCreate,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db)
    return await repo.upsert_source(data.model_dump())

@router.post("/ingest-batch", summary="Прием партии товаров")
async def ingest_batch(
    request: IngestBatchRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    _ = Depends(verify_internal_token)
):
    service = IngestionService(db, redis=redis)
    source_site_key: Optional[str] = None
    
    p_count = 0
    if request.items:
        p_count = await service.ingest_products(request.items, request.source_id, run_id=request.run_id)
    
    c_count = 0
    if request.categories:
        c_count = await service.ingest_categories(request.categories)
        
    # Keep transient run stats in Redis; persist parsing_runs only on completion/error.
    if request.source_id:
        repo = ParsingRepository(db)
        source = await repo.get_source_by_id(request.source_id)
        if source:
            source_site_key = source.site_key
        
        # Если это был discovery (были категории, но не было товаров)
        if not request.items and c_count > 0:
            await repo.update_source_stats(request.source_id, {"status": "discovery_completed", "categories_found": c_count})

        try:
            key = f"run_stats:{request.source_id}"
            existing_raw = await redis.get(key)
            existing = {}
            if existing_raw:
                try:
                    existing = json.loads(existing_raw)
                except Exception:
                    existing = {}
            await redis.set(
                key,
                json.dumps(
                    {
                        "items_scraped": int(existing.get("items_scraped", 0) or 0) + int(len(request.items or [])),
                        "items_new": int(existing.get("items_new", 0) or 0) + int(p_count or 0),
                        "categories_ingested": int(existing.get("categories_ingested", 0) or 0) + int(c_count or 0),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
                ),
                ex=24 * 3600,
            )
        except Exception:
            pass
        await db.commit()

    if p_count > 0:
        if not source_site_key and request.items:
            source_site_key = str(request.items[0].site_key or "").strip() or None
        await _publish_ops_event(
            redis,
            "catalog.updated",
            {
                "site_key": source_site_key,
                "new_items": int(p_count),
                "ts": datetime.now(timezone.utc).isoformat(),
            },
        )

    return {
        "status": "ok", 
        "items_ingested": p_count, 
        "categories_ingested": c_count
    }

@router.get("/workers", summary="Получить список активных воркеров")
async def get_active_workers(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db, redis=redis)
    return await repo.get_active_workers()

from app.schemas.parsing import ParsingErrorReport
from app.services.notifications import get_notification_service

@router.post("/sources/{source_id:int}/report-error", summary="Сообщить об ошибке парсера")
async def report_parsing_error(
    source_id: int,
    report: ParsingErrorReport,
    run_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db)
    source = await repo.report_source_error(source_id, report.error, report.is_broken)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    # Send notification via RabbitMQ
    notifier = get_notification_service()
    status_msg = "🚨 BROKEN" if report.is_broken else "⚠️ ERROR"
    text = (
        f"<b>{status_msg}: Parsing Source Failure</b>\n\n"
        f"<b>Site:</b> {source.site_key}\n"
        f"<b>URL:</b> {source.url}\n"
        f"<b>Error:</b> {report.error}"
    )
    await notifier.notify(topic="scraping", message=text, data={
        "source_id": source_id,
        "site_key": source.site_key,
        "is_broken": report.is_broken
    })

    now_utc = datetime.now(timezone.utc)
    stats_payload = None
    try:
        stats_raw = await redis.get(f"run_stats:{source_id}")
        if stats_raw:
            stats_payload = json.loads(stats_raw)
    except Exception:
        stats_payload = None

    items_scraped = int((stats_payload or {}).get("items_scraped", 0) or 0)
    items_new = int((stats_payload or {}).get("items_new", 0) or 0)
    logs_text = str((source.config or {}).get("last_logs") or "")
    duration = None
    started_at_raw = (source.config or {}).get("run_started_at")
    if isinstance(started_at_raw, str):
        try:
            started_at = datetime.fromisoformat(started_at_raw.replace("Z", "+00:00"))
            duration = max((now_utc - started_at).total_seconds(), 0.0)
        except Exception:
            duration = None

    error_run = await repo.create_parsing_run(
        source_id=source_id,
        status="error",
        items_scraped=items_scraped,
        items_new=items_new,
        error_message=report.error,
        duration_seconds=duration,
        logs=(logs_text[-100000:] if logs_text else None),
    )
    await _publish_ops_event(
        redis,
        "run.status_changed",
        {
            "run_id": int(error_run.id),
            "source_id": int(source_id),
            "site_key": source.site_key,
            "from": "running",
            "to": "error",
            "ts": now_utc.isoformat(),
        },
    )
    try:
        cfg = dict(source.config or {})
        cfg.pop("run_started_at", None)
        source.config = cfg
        await db.commit()
        await redis.delete(f"run_stats:{source_id}")
    except Exception:
        pass
    await _sync_hub_from_hub_source(db, source)
    await db.commit()
    
    return {"status": "ok"}
    
@router.post("/sources/{source_id:int}/force-run", summary="Принудительно запустить парсер")
async def force_run_parser(
    source_id: int,
    strategy: Optional[str] = None, # Allow override strategy (discovery vs deep)
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db)
    source = await repo.get_source_by_id(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
        
    from app.utils.rabbitmq import publish_parsing_task

    task = {
        "source_id": source.id,
        "url": source.url,
        "site_key": source.site_key,
        "type": source.type,
        "strategy": strategy or source.strategy,
        "config": source.config,
    }

    success = publish_parsing_task(task)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to publish task to queue")

    await repo.set_queued(source.id)
    source = await repo.get_source_by_id(source.id)
    if source:
        await _sync_hub_from_hub_source(db, source)
        await db.commit()
    await _publish_ops_event(
        redis,
        "run.status_changed",
        {
            "run_id": None,
            "source_id": int(task["source_id"]),
            "site_key": task["site_key"],
            "from": None,
            "to": "queued",
            "ts": datetime.now(timezone.utc).isoformat(),
        },
    )
    queue_stats = await _fetch_rabbit_queue_stats()
    if queue_stats.get("status") == "ok":
        await _publish_ops_event(
            redis,
            "queue.updated",
            {**queue_stats, "ts": datetime.now(timezone.utc).isoformat()},
        )
    return {"status": "ok", "message": "Task queued for immediate execution"}

@router.post("/sources/{source_id:int}/toggle", summary="Включить/выключить парсер")
async def toggle_parser(
    source_id: int,
    is_active: bool = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db)
    source = await repo.get_source_by_id(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
        
    await repo.set_source_active_status(source_id, is_active)
    source = await repo.get_source_by_id(source_id)
    if source:
        await _sync_hub_from_hub_source(db, source)
        await db.commit()
    if is_active:
        # Clear errors if re-enabling
        await repo.reset_source_error(source_id)
        
    return {"status": "ok", "is_active": is_active}

@router.post("/sources/{source_id:int}/report-status", summary="Обновить статус источника")
async def report_parsing_status(
    source_id: int,
    status: str = Body(..., embed=True),
    run_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db)
    await repo.set_source_status(source_id, status)
    source = await repo.get_source_by_id(source_id)
    now_utc = datetime.now(timezone.utc)
    if source:
        cfg = dict(source.config or {})
        if status == "running":
            cfg["run_started_at"] = now_utc.isoformat()
        source.config = cfg
        await _sync_hub_from_hub_source(db, source)
        await db.commit()

    if status == "running":
        await _publish_ops_event(
            redis,
            "run.status_changed",
            {
                "run_id": int(run_id) if isinstance(run_id, int) else None,
                "source_id": int(source_id),
                "site_key": source.site_key if source else None,
                "from": "queued",
                "to": "running",
                "ts": now_utc.isoformat(),
            },
        )
    elif status == "waiting":
        # Persist final run only on completion.
        stats_payload = None
        try:
            stats_raw = await redis.get(f"run_stats:{source_id}")
            if stats_raw:
                stats_payload = json.loads(stats_raw)
        except Exception:
            stats_payload = None

        items_scraped = int((stats_payload or {}).get("items_scraped", 0) or 0)
        items_new = int((stats_payload or {}).get("items_new", 0) or 0)
        logs_text = ""
        duration = None
        if source:
            cfg = dict(source.config or {})
            logs_text = str(cfg.get("last_logs") or "")
            started_at_raw = cfg.get("run_started_at")
            if isinstance(started_at_raw, str):
                try:
                    started_at = datetime.fromisoformat(started_at_raw.replace("Z", "+00:00"))
                    duration = max((now_utc - started_at).total_seconds(), 0.0)
                except Exception:
                    duration = None
            cfg.pop("run_started_at", None)
            source.config = cfg
            await db.commit()

        detected_error = _detect_run_error_from_logs(logs_text)
        final_status = "error" if detected_error else "completed"
        final_error_message = detected_error if detected_error else None

        completed_run = await repo.create_parsing_run(
            source_id=source_id,
            status=final_status,
            items_scraped=items_scraped,
            items_new=items_new,
            error_message=final_error_message,
            duration_seconds=duration,
            logs=(logs_text[-100000:] if logs_text else None),
        )
        try:
            await redis.delete(f"run_stats:{source_id}")
        except Exception:
            pass
        await _publish_ops_event(
            redis,
            "run.status_changed",
            {
                "run_id": int(completed_run.id),
                "source_id": int(source_id),
                "site_key": source.site_key if source else None,
                "from": "running",
                "to": final_status,
                "ts": now_utc.isoformat(),
            },
        )
    return {"status": "ok"}

@router.post("/sources/{source_id:int}/report-logs", summary="Обновить логи источника")
async def report_parsing_logs(
    source_id: int,
    logs: str = Body(..., embed=True),
    run_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db)
    trimmed_logs = logs[-100000:] if logs else logs
    await repo.update_source_logs(source_id, trimmed_logs)
    source = await repo.get_source_by_id(source_id)
    if source and source.type == "hub":
        from sqlalchemy import select
        hub = (
            await db.execute(
                select(ParsingHub).where(ParsingHub.site_key == source.site_key)
            )
        ).scalar_one_or_none()
        if hub:
            hub_cfg = dict(hub.config or {})
            hub_cfg["last_logs"] = trimmed_logs
            hub.config = hub_cfg
            await db.commit()
    if run_id:
        await repo.update_parsing_run(run_id, logs=trimmed_logs)
        await _publish_ops_event(
            redis,
            "run.log_chunk",
            {
                "run_id": int(run_id),
                "source_id": int(source_id),
                "site_key": source.site_key if source else None,
                "chunk": trimmed_logs[-1200:] if trimmed_logs else "",
                "level": "error" if (trimmed_logs and "error" in trimmed_logs.lower()) else "info",
                "ts": datetime.now(timezone.utc).isoformat(),
            },
        )
    return {"status": "ok"}

@router.get("/sources/{source_id:int}", response_model=ParsingSourceSchema, summary="Получить детали источника")
async def get_parsing_source_details(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db)
    source = await repo.get_source_by_id(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    # Needs to match ParsingSourceSchema
    # Pydantic is smart enough to map attributes, but we need to inject the extra fields
    # Using jsonable_encoder or just dict conversion might be safer if we want to combine
    # But since we return the OBJECT and Pydantic validates it... we can assign attributes dynamically 
    # IF they are not in the ORM model. But Pydantic 'from_attributes=True' will try to read from ORM.
    # ORM model doesn't have these fields.
    # So we should construct the Schema object manually.
    
    
    # If it's a hub, aggregate stats and history for the whole site
    if source.type == "hub":
        from sqlalchemy import select, func
        from app.models import DiscoveredCategory, Product

        total_items = await repo.get_total_products_count(source.site_key)
        status = await repo.get_aggregate_status(source.site_key)
        last_run_new = await repo.get_last_full_cycle_stats(source.site_key)
        history_raw = await repo.get_aggregate_history(source.site_key)
        aggregate_history_dicts = [
            {
                "date": h.day.isoformat(),
                "items_new": int(h.items_new or 0),
                "items_scraped": int(h.items_scraped or 0),
                "status": "completed"
            }
            for h in history_raw
        ]
        # Aggregate timestamps
        all_sources = await repo.get_all_sources()
        site_sources = [s for s in all_sources if s.site_key == source.site_key]
        site_list_sources = [s for s in site_sources if s.type == "list"]
        source_by_id = {s.id: s for s in site_list_sources}
        source_by_url = {s.url: s for s in site_list_sources}

        discovered_stmt = (
            select(DiscoveredCategory)
            .where(DiscoveredCategory.site_key == source.site_key)
            .order_by(DiscoveredCategory.created_at.desc())
        )
        discovered_res = await db.execute(discovered_stmt)
        discovered_categories = discovered_res.scalars().all()

        related_sources = []
        seen_urls = set()
        for cat in discovered_categories:
            runtime_source = source_by_id.get(cat.promoted_source_id) if cat.promoted_source_id else None
            if runtime_source is None:
                runtime_source = source_by_url.get(cat.url)

            related_sources.append({
                "id": runtime_source.id if runtime_source else None,
                "category_id": cat.id,
                "site_key": cat.site_key,
                "url": cat.url,
                "is_active": runtime_source.is_active if runtime_source else False,
                "status": runtime_source.status if runtime_source else f"discovered:{cat.state}",
                "last_synced_at": runtime_source.last_synced_at if runtime_source else None,
                "total_items": 0,
                "config": {
                    "discovery_name": cat.name,
                    "parent_url": cat.parent_url,
                    "category_state": cat.state,
                },
            })
            seen_urls.add(cat.url)

        # Legacy fallback: include list sources that are not yet represented in discovered_categories.
        for rel in site_list_sources:
            if rel.url in seen_urls:
                continue
            rel_cfg = rel.config or {}
            cat_name = rel_cfg.get("discovery_name")
            related_sources.append({
                "id": rel.id,
                "category_id": rel.category_id,
                "site_key": rel.site_key,
                "url": rel.url,
                "is_active": rel.is_active,
                "status": rel.status,
                "last_synced_at": rel.last_synced_at,
                "total_items": 0,
                "config": {
                    "discovery_name": cat_name,
                    "parent_url": rel_cfg.get("parent_url"),
                    "category_state": "legacy",
                },
            })

        # Fill totals in one DB query to avoid N+1 (thousands of categories can cause 500/timeouts).
        category_names = {
            str((rel.get("config") or {}).get("discovery_name")).strip()
            for rel in related_sources
            if (rel.get("config") or {}).get("discovery_name")
        }
        totals_by_category: dict[str, int] = {}
        if category_names:
            totals_rows = (
                await db.execute(
                    select(Product.category, func.count(Product.product_id))
                    .where(
                        Product.merchant == source.site_key,
                        Product.category.in_(list(category_names)),
                    )
                    .group_by(Product.category)
                )
            ).all()
            totals_by_category = {
                str(row[0]): int(row[1] or 0)
                for row in totals_rows
                if row[0]
            }
        for rel in related_sources:
            cat_name = (rel.get("config") or {}).get("discovery_name")
            if cat_name:
                rel["total_items"] = int(totals_by_category.get(str(cat_name), 0))

        last_synced = max([s.last_synced_at for s in site_sources if s.last_synced_at] or [None])
        next_sync = min([s.next_sync_at for s in site_sources] or [source.next_sync_at])
        history_dicts = []
    else:
        # It's a specific category/list
        # Total items specific to this category url
        # We assume gift_id is constructed as "site_key:product_url"
        # And product_url usually contains the category part or we can just count by what was scraped?
        # Actually parsing_runs has items_scraped, but total active items in DB?
        # We don't have a direct link from Product to Source ID. We only have gift_id.
        # But we know the source URL. GroupPrice products have /products/ ID. 
        # The relationship is weak.
        # However, for GroupPrice, we can try to filter by "category" field in Product table if we saved it?
        # We saved "category" in Product. Let's use that if possible.
        # But `upsert_products` saves `category` field.
        # Let's try to count by matching category name from source config?
        # Or just use the source URL as a filter if gift_id contains it? No.
        
        # Let's count by category name if available, otherwise 0 for now until we have better link.
        # config['discovery_name'] might match Product.category
        source_cfg = source.config or {}
        cat_name = source_cfg.get("discovery_name")
        if cat_name:
             total_items = await repo.get_total_category_products_count(source.site_key, cat_name)
        else:
             total_items = 0

        # Get detailed execution history instead of daily aggregates for the detail page
        history_raw = await repo.get_source_history(source_id, limit=20)
        history_dicts = [
            {
                "id": h.id,
                "source_id": h.source_id,
                "status": h.status,
                "items_scraped": h.items_scraped,
                "items_new": h.items_new,
                "error_message": h.error_message,
                "created_at": h.created_at
            }
            for h in history_raw
        ]
        
        last_run_new = history_raw[0].items_new if history_raw else 0
        
        status = source.status
        last_synced = source.last_synced_at
        next_sync = source.next_sync_at
        aggregate_history_dicts = []
        related_sources = []
 
    # Convert SQLAlchemy model to Pydantic compatible dict
    source_data = {c.name: getattr(source, c.name) for c in source.__table__.columns}
    source_data["status"] = status
    source_data["last_synced_at"] = last_synced
    source_data["next_sync_at"] = next_sync
    source_data["created_at"] = source.created_at
    source_data["total_items"] = total_items
    source_data["last_run_new"] = last_run_new
    source_data["history"] = history_dicts
    source_data["aggregate_history"] = aggregate_history_dicts
    source_data["related_sources"] = related_sources
    
    return source_data

@router.get("/sources/{source_id:int}/products", summary="Получить товары источника")
async def get_source_products_endpoint(
    source_id: int,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    from app.repositories.parsing import ParsingRepository
    from app.repositories.catalog import PostgresCatalogRepository
    
    parsing_repo = ParsingRepository(db)
    source = await parsing_repo.get_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
        
    catalog_repo = PostgresCatalogRepository(db)
    
    # Filter by merchant (site_key)
    # If the source has a category name in config, we could filter by category too
    category_name = None
    if source.config:
        category_name = source.config.get("discovery_name")
        
    products = await catalog_repo.get_products(
        limit=limit,
        offset=offset,
        merchant=source.site_key,
        category=category_name
    )
    
    total = await catalog_repo.count_products(
        merchant=source.site_key,
        category=category_name
    )
    
    return {"items": products, "total": total}

from app.schemas.parsing import ParsingSourceUpdate

@router.patch("/sources/{source_id:int}", response_model=ParsingSourceSchema, summary="Обновить источник парсинга")
async def update_parsing_source_endpoint(
    source_id: int,
    data: ParsingSourceUpdate,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db)
    # Filter out None values to allow partial updates
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    source = await repo.update_source(source_id, update_data)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    await _sync_hub_from_hub_source(db, source)
    await db.commit()
    await db.refresh(source)
    return source

from app.schemas.parsing import SpiderSyncRequest

@router.post("/sources/sync-spiders", summary="Синхронизировать список пауков")
async def sync_spiders_endpoint(
    request: SpiderSyncRequest,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db)
    new_spiders = await repo.sync_spiders(request.available_spiders)
    
    if new_spiders:
        notifier = get_notification_service()
        spiders_str = ", ".join(new_spiders)
        text = (
            f"<b>🆕 New Spiders Detected</b>\n\n"
            f"The following spiders were found in the codebase but missing from the DB:\n"
            f"<code>{spiders_str}</code>\n\n"
            f"They have been added to the database as <b>inactive</b>. "
            f"Please configure their URLs and settings in the admin panel."
        )
        await notifier.notify(topic="scraping", message=text)
    
    return {"status": "ok", "new_spiders": new_spiders}

@router.get("/sources/backlog", response_model=List[DiscoveredCategorySchema], summary="Получить список discovery-категорий (бэклог)")
async def get_discovery_backlog(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db)
    return await repo.get_discovered_categories(limit=limit, states=["new"])

@router.post("/sources/backlog/activate", summary="Промоут категорий из discovery-бэклога в runtime sources")
async def activate_backlog_sources(
    payload: dict = Body(default={}),
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db)
    category_ids = payload.get("category_ids") or []
    legacy_source_ids = payload.get("source_ids") or []
    ids = category_ids or legacy_source_ids
    activated_count = await repo.activate_sources(ids)
    return {"status": "ok", "activated_count": activated_count}

@router.get("/sources/backlog/stats", summary="Статистика обнаружения за 24ч")
async def get_backlog_stats(
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db)
    promoted_today = await repo.count_promoted_categories_today()
    backlog_size = len(await repo.get_discovered_categories(limit=1000, states=["new"]))
    return {"promoted_today": promoted_today, "backlog_size": backlog_size}

@router.post("/sources/run-all", summary="Запустить все активные парсеры")
async def run_all_spiders_endpoint(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db)
    sources = await repo.get_all_active_sources()
    from app.utils.rabbitmq import publish_parsing_task
    
    queued_count = 0
    failed_count = 0
    for source in sources:
        task = {
            "source_id": source.id,
            "url": source.url,
            "site_key": source.site_key,
            "type": source.type,
            "strategy": source.strategy,
            "config": source.config,
        }

        success = publish_parsing_task(task)
        if success:
            await repo.set_queued(source.id)
            queued_count += 1
            await _publish_ops_event(
                redis,
                "run.status_changed",
                {
                    "run_id": None,
                    "source_id": int(source.id),
                    "site_key": source.site_key,
                    "from": None,
                    "to": "queued",
                    "ts": datetime.now(timezone.utc).isoformat(),
                },
            )
        else:
            failed_count += 1
    queue_stats = await _fetch_rabbit_queue_stats()
    if queue_stats.get("status") == "ok":
        await _publish_ops_event(
            redis,
            "queue.updated",
            {**queue_stats, "ts": datetime.now(timezone.utc).isoformat()},
        )

    return {"status": "ok", "queued": queued_count, "failed": failed_count}

@router.delete("/sources/{source_id:int}/data", summary="Удалить все товары источника")
async def clear_source_data_endpoint(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    parsing_repo = ParsingRepository(db)
    source = await parsing_repo.get_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
        
    catalog_repo = PostgresCatalogRepository(db)
    # Products are linked to site_key, and gift_id prefix matches site_key
    count = await catalog_repo.delete_products_by_site(source.site_key)
    
    return {"status": "ok", "deleted": count}

@router.get("/sources/{source_id:int}/logs/stream", summary="Стрим логов паука в реальном времени")
async def stream_source_logs(
    source_id: int,
    redis: Redis = Depends(get_redis),
):
    """
    SSE endpoint returning logs for a specific source from Redis Pub/Sub.
    """
    async def log_generator() -> AsyncGenerator[str, None]:
        channel_name = f"logs:source:{source_id}"
        buffer_key = f"{channel_name}:buffer"
        
        # Send buffered logs first
        buffered_logs = await redis.lrange(buffer_key, 0, -1)
        for log in buffered_logs:
            yield f"data: {log}\n\n"

        pubsub = redis.pubsub()
        await pubsub.subscribe(channel_name)
        
        try:
            if not buffered_logs:
                # Send initial connection message only if there were no buffered logs
                yield "data: [CONNECTED] Real-time log stream started...\n\n"
            
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=10.0)
                if message and message['type'] == 'message':
                    data = message['data']
                    yield f"data: {data}\n\n"
                else:
                    yield "data: :ping\n\n"
        finally:
            await pubsub.unsubscribe(channel_name)
            await pubsub.close()

    return StreamingResponse(log_generator(), media_type="text/event-stream")

from app.schemas_v2 import CategoryMappingTask, CategoryBatchSubmit
from app.repositories.parsing import ParsingRepository

@router.get("/categories/tasks", response_model=List[CategoryMappingTask], summary="Получить категории для маппинга")
async def get_category_tasks(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db)
    categories = await repo.get_unmapped_categories(limit=limit)
    return [CategoryMappingTask(external_name=c.external_name) for c in categories]

@router.post("/categories/submit", summary="Сохранить результаты маппинга категорий")
async def submit_category_mappings(
    batch: CategoryBatchSubmit,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db)
    count = await repo.update_category_mappings([r.model_dump() for r in batch.results])
    return {"status": "ok", "updated": count}

from app.repositories.telegram import TelegramRepository
from pydantic import BaseModel
import hashlib

class SubscriberUpdate(BaseModel):
    chat_id: int
    name: Optional[str] = None
    slug: Optional[str] = None

def _hash_invite_password(password: str) -> str:
    secret = settings.secret_key or "change-me-in-production"
    raw = f"{secret}:{password}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class InviteCreate(BaseModel):
    username: str
    password: str
    name: Optional[str] = None
    mentor_id: Optional[int] = None
    permissions: Optional[List[str]] = None


class InviteClaim(BaseModel):
    username: str
    password: str
    chat_id: int
    name: Optional[str] = None
@router.get("/telegram/subscribers", summary="Получить список всех подписчиков")
async def list_telegram_subscribers(
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = TelegramRepository(db)
    return await repo.get_all_subscribers()

@router.get("/telegram/subscribers/{chat_id}")
async def get_telegram_subscriber(
    chat_id: int,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = TelegramRepository(db)
    sub = await repo.get_subscriber(chat_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    return sub

@router.get("/telegram/subscribers/by-username/{username}")
async def get_telegram_subscriber_by_username(
    username: str,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = TelegramRepository(db)
    slug = username.strip().lstrip("@").lower()
    sub = await repo.get_subscriber_by_slug(slug)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    return sub
@router.post("/telegram/subscribers")
async def create_telegram_subscriber(
    data: SubscriberUpdate,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = TelegramRepository(db)
    sub = await repo.create_subscriber(data.chat_id, data.name, data.slug)
    return sub

@router.post("/telegram/invites")
async def create_telegram_invite(
    data: InviteCreate,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = TelegramRepository(db)
    slug = data.username.strip().lstrip("@").lower()
    if not slug:
        raise HTTPException(status_code=400, detail="Invalid username")
    existing = await repo.get_subscriber_by_slug(slug)
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")
    if data.mentor_id is not None:
        mentor = await repo.get_subscriber_by_id(data.mentor_id)
        if not mentor:
            raise HTTPException(status_code=400, detail="Mentor not found")
    sub = await repo.create_invite(
        slug=slug,
        name=data.name,
        password_hash=_hash_invite_password(data.password),
        mentor_id=data.mentor_id,
        permissions=data.permissions or [],
    )
    return sub


@router.post("/telegram/invites/claim")
async def claim_telegram_invite(
    data: InviteClaim,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = TelegramRepository(db)
    slug = data.username.strip().lstrip("@").lower()
    sub = await repo.claim_invite(
        slug=slug,
        password_hash=_hash_invite_password(data.password),
        chat_id=data.chat_id,
        name=data.name,
    )
    if not sub:
        raise HTTPException(status_code=404, detail="Invite not found or password invalid")
    return sub
@router.post("/telegram/subscribers/{chat_id}/role")
async def set_subscriber_role(
    chat_id: int,
    role: str,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = TelegramRepository(db)
    success = await repo.set_role(chat_id, role)
    if not success:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    return {"status": "ok"}

@router.post("/telegram/subscribers/{chat_id}/permissions")
async def set_subscriber_permissions(
    chat_id: int,
    perms: List[str],
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = TelegramRepository(db)
    success = await repo.set_permissions(chat_id, perms)
    if not success:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    return {"status": "ok"}

@router.post("/telegram/subscribers/{chat_id}/subscribe")
async def subscribe_telegram_topic(
    chat_id: int,
    topic: str,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = TelegramRepository(db)
    success = await repo.subscribe_topic(chat_id, topic)
    return {"status": "ok" if success else "error"}

@router.post("/telegram/subscribers/{chat_id}/unsubscribe")
async def unsubscribe_telegram_topic(
    chat_id: int,
    topic: str,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = TelegramRepository(db)
    success = await repo.unsubscribe_topic(chat_id, topic)
    return {"status": "ok" if success else "error"}

@router.get("/telegram/topics/{topic}/subscribers")
async def get_topic_subscribers(
    topic: str,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = TelegramRepository(db)
    subscribers = await repo.get_subscribers_for_topic(topic)
    return subscribers

@router.post("/telegram/subscribers/{chat_id}/language")
async def set_telegram_language(
    chat_id: int,
    language: str = Query(...),
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = TelegramRepository(db)
    success = await repo.set_language(chat_id, language)
    return {"status": "ok" if success else "error"}
@router.post("/webapp/auth", summary="Авторизация через Telegram WebApp")
async def webapp_auth(
    init_data: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
):
    import logging
    logger = logging.getLogger("webapp_auth")
    logger.info(f"Webapp auth attempt. Init data length: {len(init_data)}")
    
    if not settings.telegram_bot_token:
        logger.error("Bot token not configured")
        raise HTTPException(status_code=500, detail="Bot token not configured")
        
    # Dev bypass
    if settings.env == "dev" and init_data == "dev_user_1821014162":
        logger.info("Using DEV BYPASS authentication for user 1821014162")
        user_id = 1821014162
    else:
        if not verify_telegram_init_data(init_data, settings.telegram_bot_token):
            logger.warning("Invalid init data verification failed")
            raise HTTPException(status_code=403, detail="Invalid init data")
            
        from urllib.parse import parse_qsl
        import json
        
        params = dict(parse_qsl(init_data))
        user_data = json.loads(params.get("user", "{}"))
        user_id = int(user_data.get("id", 0))
    
    logger.info(f"User ID from init_data: {user_id}")
    
    if not user_id:
        logger.warning("User ID not found in init data")
        raise HTTPException(status_code=400, detail="User ID not found in init data")
        
    repo = TelegramRepository(db)
    subscriber = await repo.get_subscriber(user_id)
    
    if not subscriber:
        logger.warning(f"Subscriber not found for {user_id}")
        
    if subscriber:
        logger.info(f"Subscriber found: {subscriber.chat_id}, Role: {subscriber.role}")

    if not subscriber or subscriber.role not in ["admin", "superadmin"]:
        logger.warning(f"Access denied for {user_id}. Role: {subscriber.role if subscriber else 'None'}")
        raise HTTPException(status_code=403, detail="Access denied")
        
    logger.info(f"Auth successful for {user_id}")
    return {
        "status": "ok",
        "user": {
            "id": subscriber.chat_id,
            "name": subscriber.name,
            "role": subscriber.role,
            "permissions": subscriber.permissions
        }
    }


@router.get("/products")
async def get_products_endpoint(
    limit: int = 50,
    offset: int = 0,
    is_active: Optional[bool] = None,
    merchant: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    from app.repositories.catalog import PostgresCatalogRepository
    from sqlalchemy import text
    repo = PostgresCatalogRepository(db)
    products = await repo.get_products(
        limit=limit, 
        offset=offset, 
        is_active=is_active, 
        merchant=merchant, 
        search=search
    )
    total = await repo.count_products(
        is_active=is_active, 
        merchant=merchant, 
        search=search
    )

    # Enrich with "scraped from site" category (discovered_categories) via product_category_links.
    product_ids = [p.product_id for p in (products or []) if getattr(p, "product_id", None)]
    latest_cat_by_product: dict[str, dict] = {}
    cat_counts: dict[str, int] = {}
    if product_ids:
        # total categories per product
        rows = (
            await db.execute(
                text(
                    """
                    SELECT product_id, COUNT(*)::int AS cnt
                    FROM product_category_links
                    WHERE product_id = ANY(:ids)
                    GROUP BY product_id
                    """
                ),
                {"ids": product_ids},
            )
        ).mappings().all()
        cat_counts = {r["product_id"]: int(r["cnt"]) for r in rows if r.get("product_id")}

        # latest category per product by last_seen_at
        rows = (
            await db.execute(
                text(
                    """
                    SELECT DISTINCT ON (pcl.product_id)
                        pcl.product_id,
                        dc.id AS category_id,
                        dc.name AS category_name,
                        dc.url AS category_url,
                        pcl.last_seen_at
                    FROM product_category_links pcl
                    JOIN discovered_categories dc
                        ON dc.id = pcl.discovered_category_id
                    WHERE pcl.product_id = ANY(:ids)
                    ORDER BY pcl.product_id, pcl.last_seen_at DESC
                    """
                ),
                {"ids": product_ids},
            )
        ).mappings().all()
        for r in rows:
            pid = r.get("product_id")
            if not pid:
                continue
            latest_cat_by_product[pid] = {
                "id": r.get("category_id"),
                "name": r.get("category_name"),
                "url": r.get("category_url"),
                "last_seen_at": r.get("last_seen_at").isoformat() if r.get("last_seen_at") else None,
            }

    items = []
    for p in products or []:
        pid = p.product_id
        items.append(
            {
                "product_id": pid,
                "gift_id": pid,  # backwards-compat for older clients
                "title": p.title,
                "description": p.description,
                "price": float(p.price) if p.price is not None else None,
                "currency": p.currency,
                "image_url": p.image_url,
                "product_url": p.product_url,
                "merchant": p.merchant,
                # Internal category (our own classification) - may be NULL.
                "category": p.category,
                # External/site category provenance
                "scraped_category": latest_cat_by_product.get(pid),
                "scraped_categories_count": cat_counts.get(pid, 0),
                "site_key": getattr(p, "site_key", None),
                "is_active": p.is_active,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            }
        )

    return {"items": items, "total": total}


@router.get("/merchants", summary="List merchant metadata (store sites)")
async def list_merchants(
    limit: int = 200,
    offset: int = 0,
    q: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token),
):
    from sqlalchemy import or_, func
    from app.models import Merchant

    limit = max(1, min(limit, 500))
    offset = max(0, offset)

    stmt = sa.select(Merchant)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Merchant.site_key.ilike(like), Merchant.name.ilike(like)))
    stmt = stmt.order_by(Merchant.site_key.asc()).offset(offset).limit(limit)
    items = (await db.execute(stmt)).scalars().all()

    count_stmt = sa.select(func.count()).select_from(Merchant)
    if q:
        like = f"%{q}%"
        count_stmt = count_stmt.where(or_(Merchant.site_key.ilike(like), Merchant.name.ilike(like)))
    total = (await db.execute(count_stmt)).scalar() or 0

    return {
        "items": [
            {
                "site_key": m.site_key,
                "name": m.name,
                "base_url": m.base_url,
                "meta": m.meta,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "updated_at": m.updated_at.isoformat() if m.updated_at else None,
            }
            for m in items
        ],
        "total": total,
    }


@router.patch("/merchants/{site_key}", summary="Update merchant metadata")
async def update_merchant(
    site_key: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token),
):
    from app.models import Merchant
    key = (site_key or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="site_key is required")

    name = payload.get("name")
    base_url = payload.get("base_url")

    merchant = (await db.execute(sa.select(Merchant).where(Merchant.site_key == key))).scalar_one_or_none()
    if not merchant:
        merchant = Merchant(site_key=key, name=key)
        db.add(merchant)
        await db.flush()

    if name is not None:
        merchant.name = str(name).strip() or key
    if base_url is not None:
        merchant.base_url = str(base_url).strip() or None

    await db.commit()

    return {
        "ok": True,
        "item": {
            "site_key": merchant.site_key,
            "name": merchant.name,
            "base_url": merchant.base_url,
            "meta": merchant.meta,
            "created_at": merchant.created_at.isoformat() if merchant.created_at else None,
            "updated_at": merchant.updated_at.isoformat() if merchant.updated_at else None,
        },
    }


@router.get("/queues/stats")
async def get_queue_stats(
    _ = Depends(verify_internal_token)
):
    return await _fetch_rabbit_queue_stats()


@router.get("/queues/tasks")
async def get_queue_tasks(
    limit: int = 50,
    _=Depends(verify_internal_token)
):
    import httpx
    import os

    rabbit_url = os.getenv("RABBITMQ_MANAGEMENT_URL", "http://guest:guest@rabbitmq:15672/api/queues/%2f/parsing_tasks")
    rabbit_get_url = rabbit_url.rstrip("/") + "/get"

    payload = {
        "count": max(1, min(limit, 200)),
        "ackmode": "ack_requeue_true",
        "encoding": "auto",
        "truncate": 50000
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(rabbit_get_url, json=payload)
            if resp.status_code != 200:
                return {"status": "error", "message": f"RabbitMQ API returned {resp.status_code}", "items": []}

            raw_items = resp.json() if isinstance(resp.json(), list) else []
            items = []
            for i, msg in enumerate(raw_items):
                payload_data = msg.get("payload")
                parsed = payload_data if isinstance(payload_data, dict) else {}
                if not parsed and isinstance(payload_data, str):
                    try:
                        import json
                        parsed = json.loads(payload_data)
                    except Exception:
                        parsed = {"raw_payload": payload_data}

                items.append({
                    "idx": i,
                    "routing_key": msg.get("routing_key"),
                    "redelivered": msg.get("redelivered", False),
                    "exchange": msg.get("exchange"),
                    "payload_bytes": msg.get("payload_bytes"),
                    "properties": msg.get("properties", {}),
                    "task": parsed,
                })

            return {
                "status": "ok",
                "queue_name": "parsing_tasks",
                "count": len(items),
                "items": items
            }
    except Exception as e:
        return {"status": "error", "message": str(e), "items": []}


@router.get("/queues/history")
async def get_queue_history(
    limit: int = 100,
    offset: int = 0,
    status: Optional[str] = Query(None),
    _=Depends(verify_internal_token),
    db: AsyncSession = Depends(get_db),
):
    from datetime import timezone
    from sqlalchemy import select, func
    from app.models import ParsingRun, ParsingSource, DiscoveredCategory

    def calc_duration_seconds(run: ParsingRun) -> Optional[float]:
        if isinstance(run.duration_seconds, (int, float)):
            return float(run.duration_seconds)
        if run.status not in {"completed", "error"}:
            return None
        if run.created_at and run.updated_at:
            created_at = run.created_at
            updated_at = run.updated_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)
            duration = (updated_at - created_at).total_seconds()
            return max(duration, 0.0)
        return None

    allowed_statuses = {"completed", "error"}
    status_filter = str(status or "").strip().lower()
    if status_filter and status_filter not in allowed_statuses:
        raise HTTPException(status_code=400, detail="status must be one of: completed,error")

    where_clause = (
        (ParsingRun.status == status_filter)
        if status_filter
        else ParsingRun.status.in_(("completed", "error"))
    )

    safe_limit = max(1, min(limit, 500))
    safe_offset = max(0, int(offset))

    total_stmt = (
        select(func.count(ParsingRun.id))
        .join(ParsingSource, ParsingRun.source_id == ParsingSource.id)
        .where(where_clause)
    )
    total = int((await db.execute(total_stmt)).scalar() or 0)

    stmt = (
        select(ParsingRun, ParsingSource, DiscoveredCategory)
        .join(ParsingSource, ParsingRun.source_id == ParsingSource.id)
        .outerjoin(DiscoveredCategory, ParsingSource.category_id == DiscoveredCategory.id)
        .where(where_clause)
        .order_by(ParsingRun.created_at.desc())
        .offset(safe_offset)
        .limit(safe_limit)
    )
    res = await db.execute(stmt)

    items = []
    for run, source, category in res.all():
        categories_scraped = _extract_categories_scraped_from_logs(run.logs)
        category_name = None
        if source.type == "list":
            category_name = (category.name if category else None) or ((source.config or {}).get("discovery_name"))
        items.append({
            "id": run.id,
            "source_id": run.source_id,
            "site_key": source.site_key,
            "source_type": source.type,
            "strategy": source.strategy,
            "source_name": (source.config or {}).get("discovery_name"),
            "source_url": source.url,
            "category_name": category_name,
            "status": run.status,
            "items_scraped": run.items_scraped,
            "categories_scraped": categories_scraped,
            "items_new": run.items_new,
            "error_message": run.error_message,
            "duration_seconds": calc_duration_seconds(run),
            "created_at": run.created_at,
            "updated_at": run.updated_at,
            "logs_excerpt": (run.logs[-600:] if run.logs else None),
        })

    return {
        "status": "ok",
        "count": len(items),
        "total": total,
        "limit": safe_limit,
        "offset": safe_offset,
        "items": items,
    }


@router.get("/queues/history/{run_id}")
async def get_queue_history_run_details(
    run_id: int,
    _=Depends(verify_internal_token),
    db: AsyncSession = Depends(get_db),
):
    from datetime import timezone
    from sqlalchemy import select
    from app.models import ParsingRun, ParsingSource, DiscoveredCategory

    stmt = (
        select(ParsingRun, ParsingSource, DiscoveredCategory)
        .join(ParsingSource, ParsingRun.source_id == ParsingSource.id)
        .outerjoin(DiscoveredCategory, ParsingSource.category_id == DiscoveredCategory.id)
        .where(ParsingRun.id == run_id)
    )
    res = await db.execute(stmt)
    row = res.first()
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")

    run, source, category = row
    categories_scraped = _extract_categories_scraped_from_logs(run.logs)
    duration_seconds = run.duration_seconds
    if duration_seconds is None and run.status in {"completed", "error"} and run.created_at and run.updated_at:
        created_at = run.created_at
        updated_at = run.updated_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        duration_seconds = max((updated_at - created_at).total_seconds(), 0.0)

    category_name = None
    if source.type == "list":
        category_name = (category.name if category else None) or ((source.config or {}).get("discovery_name"))

    return {
        "status": "ok",
        "item": {
            "id": run.id,
            "source_id": run.source_id,
            "site_key": source.site_key,
            "source_url": source.url,
            "strategy": source.strategy,
            "source_type": source.type,
            "category_name": category_name,
            "run_status": run.status,
            "items_scraped": run.items_scraped,
            "categories_scraped": categories_scraped,
            "items_new": run.items_new,
            "error_message": run.error_message,
            "duration_seconds": duration_seconds,
            "created_at": run.created_at,
            "updated_at": run.updated_at,
            "logs": run.logs or "",
        },
    }


@router.get("/ops/overview")
async def get_ops_overview(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    force_fresh: bool = Query(False),
    _=Depends(verify_internal_token),
):
    settings_state = await _get_or_create_ops_runtime_state(db)
    cache_key = _snapshot_key("overview")
    settings_payload = _serialize_ops_runtime_settings(settings_state)["item"]
    snapshot_ttl_ms = int(settings_payload["ops_snapshot_ttl_ms"])
    stale_max_age_ms = int(settings_payload["ops_stale_max_age_ms"])
    aggregator_enabled = bool(settings_payload.get("ops_aggregator_enabled"))
    if not force_fresh:
        cached = await _snapshot_read(redis, cache_key)
        if cached and isinstance(cached.get("payload"), dict):
            stale = _is_snapshot_stale(cached.get("generated_at"), stale_max_age_ms)
            if not stale:
                ops_snapshot_cache_hits_total.inc()
                return _add_snapshot_meta_fields(cached["payload"], cache_key=cache_key, generated_at=cached.get("generated_at"), stale=False)
            if aggregator_enabled:
                ops_snapshot_stale_served_total.inc()
                await _trigger_snapshot_refresh_if_needed(
                    redis=redis,
                    cache_key=cache_key,
                    block="overview",
                    ttl_ms=snapshot_ttl_ms,
                    compute_fn=lambda: _compute_ops_overview_payload(db=db, redis=redis),
                )
                return _add_snapshot_meta_fields(cached["payload"], cache_key=cache_key, generated_at=cached.get("generated_at"), stale=True)
        ops_snapshot_cache_misses_total.inc()

    payload = await _compute_ops_overview_payload(db=db, redis=redis)
    generated_at = datetime.now(timezone.utc).isoformat()
    try:
        wrapped, changed = await _snapshot_write(
            redis,
            block="overview",
            key=cache_key,
            payload=payload,
            ttl_ms=snapshot_ttl_ms,
        )
        generated_at = wrapped.get("generated_at") or generated_at
        if changed:
            await _publish_ops_event(
                redis,
                "ops.snapshot.updated",
                {
                    "block": "overview",
                    "key": cache_key,
                    "version": (await _snapshot_meta_get(redis)).get(cache_key, {}).get("version", 0),
                    "generated_at": generated_at,
                },
            )
    except Exception:
        ops_snapshot_refresh_errors_total.inc()
        logger.warning("ops overview served in degraded mode (redis unavailable)")
    return _add_snapshot_meta_fields(payload, cache_key=cache_key, generated_at=generated_at, stale=False)


async def _compute_ops_overview_payload(
    *,
    db: AsyncSession,
    redis: Redis,
) -> dict[str, Any]:
    from sqlalchemy import select, func

    await _maybe_reconcile_queued_runs_with_rabbit(db)

    queue = await _fetch_rabbit_queue_stats()
    workers = await ParsingRepository(db, redis=redis).get_active_workers()

    status_stmt = (
        select(ParsingRun.status, func.count(ParsingRun.id))
        .group_by(ParsingRun.status)
    )
    status_res = await db.execute(status_stmt)
    run_status = {row[0]: int(row[1]) for row in status_res.all()}
    run_status["queued"] = int(queue.get("messages_total", 0) or 0)
    run_status["running"] = int(
        sum(len((w or {}).get("active_tasks") or []) for w in workers)
    )

    now_utc = datetime.now(timezone.utc)

    disc_stmt = (
        select(DiscoveredCategory.state, func.count(DiscoveredCategory.id))
        .group_by(DiscoveredCategory.state)
    )
    disc_res = await db.execute(disc_stmt)
    discovery_categories = {row[0]: int(row[1]) for row in disc_res.all()}

    products_total = int(
        (
            await db.execute(
                select(func.count(Product.product_id))
            )
        ).scalar()
        or 0
    )
    products_new_24h = int(
        (
            await db.execute(
                select(func.count(Product.product_id)).where(
                    Product.created_at >= now_utc - timedelta(hours=24)
                )
            )
        ).scalar()
        or 0
    )

    sources_stmt = select(func.count(ParsingSource.id)).where(ParsingSource.is_active.is_(True))
    active_sources = int((await db.execute(sources_stmt)).scalar() or 0)

    await _append_ops_task_snapshot(
        redis,
        ts=now_utc,
        queue_total=int(queue.get("messages_total", 0) or 0),
        running_total=int(run_status.get("running", 0) or 0),
        completed_total=int(run_status.get("completed", 0) or 0),
        error_total=int(run_status.get("error", 0) or 0),
    )

    return {
        "status": "ok",
        "queue": queue,
        "workers": {
            "online": len(workers),
            "items": workers,
        },
        "runs": run_status,
        "discovery": discovery_categories,  # backward-compat
        "discovery_categories": discovery_categories,
        "discovery_products": {
            "new_24h": products_new_24h,
            "total": products_total,
        },
        "active_sources": active_sources,
        "ts": now_utc.isoformat(),
    }


@router.post("/ops/workers/{worker_id}/pause")
async def pause_ops_worker(
    worker_id: str,
    redis: Redis = Depends(get_redis),
    _=Depends(verify_internal_token),
):
    worker_id = str(worker_id or "").strip()
    if not worker_id:
        raise HTTPException(status_code=400, detail="worker_id is required")
    await redis.set(f"worker_pause:{worker_id}", "1")
    await redis.publish(
        OPS_EVENTS_CHANNEL,
        json.dumps(
            {
                "type": "worker.pause_changed",
                "payload": {
                    "worker_id": worker_id,
                    "paused": True,
                    "ts": datetime.now(timezone.utc).isoformat(),
                },
            }
        ),
    )
    return {"status": "ok", "worker_id": worker_id, "paused": True}


@router.post("/ops/workers/{worker_id}/resume")
async def resume_ops_worker(
    worker_id: str,
    redis: Redis = Depends(get_redis),
    _=Depends(verify_internal_token),
):
    worker_id = str(worker_id or "").strip()
    if not worker_id:
        raise HTTPException(status_code=400, detail="worker_id is required")
    await redis.delete(f"worker_pause:{worker_id}")
    await redis.publish(
        OPS_EVENTS_CHANNEL,
        json.dumps(
            {
                "type": "worker.pause_changed",
                "payload": {
                    "worker_id": worker_id,
                    "paused": False,
                    "ts": datetime.now(timezone.utc).isoformat(),
                },
            }
        ),
    )
    return {"status": "ok", "worker_id": worker_id, "paused": False}


@router.get("/ops/tasks-trend")
async def get_ops_tasks_trend(
    granularity: str = Query("day"),
    buckets: Optional[int] = Query(None, ge=1, le=1000),
    force_fresh: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    _=Depends(verify_internal_token),
):
    settings_state = await _get_or_create_ops_runtime_state(db)
    settings_payload = _serialize_ops_runtime_settings(settings_state)["item"]
    snapshot_ttl_ms = int(settings_payload["ops_snapshot_ttl_ms"])
    stale_max_age_ms = int(settings_payload["ops_stale_max_age_ms"])
    aggregator_enabled = bool(settings_payload.get("ops_aggregator_enabled"))
    g = str(granularity or "day").strip().lower()
    default_buckets = {"week": 12, "day": 30, "hour": 72, "minute": 180}
    bucket_count = int(buckets if buckets is not None else default_buckets.get(g, 30))
    cache_key = _snapshot_key("tasks_trend", granularity=g, buckets=bucket_count)
    if not force_fresh:
        cached = await _snapshot_read(redis, cache_key)
        if cached and isinstance(cached.get("payload"), dict):
            stale = _is_snapshot_stale(cached.get("generated_at"), stale_max_age_ms)
            if not stale:
                ops_snapshot_cache_hits_total.inc()
                return _add_snapshot_meta_fields(cached["payload"], cache_key=cache_key, generated_at=cached.get("generated_at"), stale=False)
            if aggregator_enabled:
                ops_snapshot_stale_served_total.inc()
                await _trigger_snapshot_refresh_if_needed(
                    redis=redis,
                    cache_key=cache_key,
                    block="tasks_trend",
                    ttl_ms=snapshot_ttl_ms,
                    compute_fn=lambda: _compute_ops_tasks_trend_payload(granularity=granularity, buckets=buckets, redis=redis),
                )
                return _add_snapshot_meta_fields(cached["payload"], cache_key=cache_key, generated_at=cached.get("generated_at"), stale=True)
        ops_snapshot_cache_misses_total.inc()

    payload = await _compute_ops_tasks_trend_payload(granularity=granularity, buckets=buckets, redis=redis)
    generated_at = datetime.now(timezone.utc).isoformat()
    try:
        wrapped, changed = await _snapshot_write(
            redis,
            block="tasks_trend",
            key=cache_key,
            payload=payload,
            ttl_ms=snapshot_ttl_ms,
        )
        generated_at = wrapped.get("generated_at") or generated_at
        if changed:
            meta = await _snapshot_meta_get(redis)
            await _publish_ops_event(
                redis,
                "ops.snapshot.updated",
                {
                    "block": "tasks_trend",
                    "key": cache_key,
                    "version": meta.get(cache_key, {}).get("version", 0),
                    "generated_at": generated_at,
                },
            )
    except Exception:
        ops_snapshot_refresh_errors_total.inc()
        logger.warning("ops tasks trend served in degraded mode (redis unavailable)")
    return _add_snapshot_meta_fields(payload, cache_key=cache_key, generated_at=generated_at, stale=False)


async def _compute_ops_tasks_trend_payload(
    *,
    granularity: str,
    buckets: Optional[int],
    redis: Redis,
) -> dict[str, Any]:
    now_utc = datetime.now(timezone.utc)
    g = str(granularity or "day").strip().lower()
    if g not in {"week", "day", "hour", "minute"}:
        raise HTTPException(status_code=400, detail="granularity must be one of: week,day,hour,minute")

    default_buckets = {
        "week": 12,
        "day": 30,
        "hour": 72,
        "minute": 180,
    }
    bucket_count = int(buckets if buckets is not None else default_buckets[g])

    if g == "week":
        step = timedelta(weeks=1)
    elif g == "day":
        step = timedelta(days=1)
    elif g == "hour":
        step = timedelta(hours=1)
    else:
        step = timedelta(minutes=1)

    def bucket_start(dt: datetime) -> datetime:
        dt = dt.astimezone(timezone.utc)
        if g == "week":
            start = datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)
            return start - timedelta(days=start.weekday())
        if g == "day":
            return datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)
        if g == "hour":
            return datetime(dt.year, dt.month, dt.day, dt.hour, tzinfo=timezone.utc)
        return datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute, tzinfo=timezone.utc)

    end_bucket = bucket_start(now_utc)
    start_bucket = end_bucket - step * max(0, bucket_count - 1)
    buckets_map: dict[str, dict] = {}
    cursor = start_bucket
    for _ in range(bucket_count):
        key = cursor.isoformat()
        buckets_map[key] = {
            "date": key,
            "queue": 0,
            "running": 0,
            "success": 0,
            "error": 0,
        }
        cursor = cursor + step

    raw = await redis.lrange(OPS_TASK_SNAPSHOTS_KEY, 0, OPS_TASK_SNAPSHOTS_MAX - 1)
    snapshots: list[dict] = []
    for payload in reversed(raw):
        try:
            item = json.loads(payload)
            ts_raw = item.get("ts")
            if not isinstance(ts_raw, str):
                continue
            ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            snapshots.append(
                {
                    "ts": ts,
                    "queue": int(item.get("queue", 0) or 0),
                    "running": int(item.get("running", 0) or 0),
                    "completed_total": int(item.get("completed_total", 0) or 0),
                    "error_total": int(item.get("error_total", 0) or 0),
                }
            )
        except Exception:
            continue

    previous_completed: Optional[int] = None
    previous_error: Optional[int] = None
    for snap in snapshots:
        ts = snap["ts"]
        if ts < start_bucket:
            previous_completed = snap["completed_total"]
            previous_error = snap["error_total"]
            continue
        b = bucket_start(ts).isoformat()
        if b not in buckets_map:
            continue
        bucket = buckets_map[b]
        bucket["queue"] = max(int(bucket["queue"]), int(snap["queue"]))
        bucket["running"] = max(int(bucket["running"]), int(snap["running"]))

        completed_total = int(snap["completed_total"])
        error_total = int(snap["error_total"])
        if previous_completed is not None:
            bucket["success"] += max(0, completed_total - previous_completed)
        if previous_error is not None:
            bucket["error"] += max(0, error_total - previous_error)
        previous_completed = completed_total
        previous_error = error_total

    items = list(buckets_map.values())
    return {
        "status": "ok",
        "granularity": g,
        "buckets": bucket_count,
        "items": items,
        "totals": {
            "queue_max": max((int(x["queue"] or 0) for x in items), default=0),
            "running_max": max((int(x["running"] or 0) for x in items), default=0),
            "success": sum(int(x["success"] or 0) for x in items),
            "error": sum(int(x["error"] or 0) for x in items),
        },
        "generated_at": now_utc.isoformat(),
    }


@router.post("/ops/scheduler/pause")
async def pause_ops_scheduler(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    _=Depends(verify_internal_token),
):
    await _set_scheduler_paused_state(db, True)
    try:
        await redis.set(OPS_SCHEDULER_PAUSE_KEY, "1")
    except Exception:
        pass
    await _publish_ops_event(
        redis,
        "scheduler.pause_changed",
        {
            "paused": True,
            "ts": datetime.now(timezone.utc).isoformat(),
        },
    )
    return {"status": "ok", "paused": True}


@router.post("/ops/scheduler/resume")
async def resume_ops_scheduler(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    _=Depends(verify_internal_token),
):
    await _set_scheduler_paused_state(db, False)
    try:
        await redis.delete(OPS_SCHEDULER_PAUSE_KEY)
    except Exception:
        pass
    await _publish_ops_event(
        redis,
        "scheduler.pause_changed",
        {
            "paused": False,
            "ts": datetime.now(timezone.utc).isoformat(),
        },
    )
    return {"status": "ok", "paused": False}


@router.get("/ops/runtime-settings")
async def get_ops_runtime_settings(
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_internal_token),
):
    state = await _get_or_create_ops_runtime_state(db)
    return _serialize_ops_runtime_settings(state)


@router.put("/ops/runtime-settings")
async def update_ops_runtime_settings(
    data: OpsRuntimeSettingsUpdateRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    principal: str = Depends(verify_internal_token),
):
    state = await _get_or_create_ops_runtime_state(db)
    actor_id = _ops_actor_id_from_principal(principal)
    throttle_key = f"ops:runtime-settings:rate:{hashlib.sha1(principal.encode('utf-8')).hexdigest()}"  # nosec B324
    try:
        allowed = await redis.set(throttle_key, "1", px=OPS_SETTINGS_UPDATE_RATE_LIMIT_MS, nx=True)
        if not allowed:
            raise HTTPException(status_code=429, detail="Too many settings updates. Please retry in a moment.")
    except HTTPException:
        raise
    except Exception:
        # Redis unavailable: do not block updates, just skip limiter.
        pass
    payload = data.model_dump(exclude_unset=True)
    if "ops_client_intervals" in payload:
        incoming = payload.get("ops_client_intervals")
        if not isinstance(incoming, dict):
            raise HTTPException(status_code=400, detail="ops_client_intervals must be an object")
        for key, value in incoming.items():
            if key not in OPS_CLIENT_INTERVAL_DEFAULTS:
                raise HTTPException(status_code=400, detail=f"Unknown interval key: {key}")
            try:
                num = int(value)
            except Exception:
                raise HTTPException(status_code=400, detail=f"Invalid interval value for {key}")
            if num < OPS_INTERVAL_MIN_MS or num > OPS_INTERVAL_MAX_MS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Interval for {key} must be between {OPS_INTERVAL_MIN_MS} and {OPS_INTERVAL_MAX_MS}",
                )
        merged = _normalize_client_intervals({**(state.ops_client_intervals or {}), **incoming})
        state.ops_client_intervals = merged

    if "ops_aggregator_enabled" in payload:
        state.ops_aggregator_enabled = bool(payload["ops_aggregator_enabled"])
    if "ops_aggregator_interval_ms" in payload:
        state.ops_aggregator_interval_ms = int(payload["ops_aggregator_interval_ms"])
    if "ops_snapshot_ttl_ms" in payload:
        state.ops_snapshot_ttl_ms = int(payload["ops_snapshot_ttl_ms"])
    if "ops_stale_max_age_ms" in payload:
        state.ops_stale_max_age_ms = int(payload["ops_stale_max_age_ms"])

    state.settings_version = int(state.settings_version or 1) + 1
    state.updated_by = actor_id
    state.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(state)
    ops_settings_updates_total.inc()

    event_payload = {
        "settings_version": int(state.settings_version or 1),
        "updated_at": _iso(state.updated_at),
    }
    await _publish_ops_event(redis, "ops.settings.updated", event_payload)
    return _serialize_ops_runtime_settings(state)


@router.get("/ops/scheduler/stats")
async def get_ops_scheduler_stats(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    force_fresh: bool = Query(False),
    _=Depends(verify_internal_token),
):
    settings_state = await _get_or_create_ops_runtime_state(db)
    settings_payload = _serialize_ops_runtime_settings(settings_state)["item"]
    snapshot_ttl_ms = int(settings_payload["ops_snapshot_ttl_ms"])
    stale_max_age_ms = int(settings_payload["ops_stale_max_age_ms"])
    aggregator_enabled = bool(settings_payload.get("ops_aggregator_enabled"))
    cache_key = _snapshot_key("scheduler_stats")
    if not force_fresh:
        cached = await _snapshot_read(redis, cache_key)
        if cached and isinstance(cached.get("payload"), dict):
            stale = _is_snapshot_stale(cached.get("generated_at"), stale_max_age_ms)
            if not stale:
                ops_snapshot_cache_hits_total.inc()
                return _add_snapshot_meta_fields(cached["payload"], cache_key=cache_key, generated_at=cached.get("generated_at"), stale=False)
            if aggregator_enabled:
                ops_snapshot_stale_served_total.inc()
                await _trigger_snapshot_refresh_if_needed(
                    redis=redis,
                    cache_key=cache_key,
                    block="scheduler_stats",
                    ttl_ms=snapshot_ttl_ms,
                    compute_fn=lambda: _compute_ops_scheduler_stats_payload(db=db),
                )
                return _add_snapshot_meta_fields(cached["payload"], cache_key=cache_key, generated_at=cached.get("generated_at"), stale=True)
        ops_snapshot_cache_misses_total.inc()

    payload = await _compute_ops_scheduler_stats_payload(db=db)
    generated_at = datetime.now(timezone.utc).isoformat()
    try:
        wrapped, changed = await _snapshot_write(
            redis,
            block="scheduler_stats",
            key=cache_key,
            payload=payload,
            ttl_ms=snapshot_ttl_ms,
        )
        generated_at = wrapped.get("generated_at") or generated_at
        if changed:
            meta = await _snapshot_meta_get(redis)
            await _publish_ops_event(
                redis,
                "ops.snapshot.updated",
                {
                    "block": "scheduler_stats",
                    "key": cache_key,
                    "version": meta.get(cache_key, {}).get("version", 0),
                    "generated_at": generated_at,
                },
            )
    except Exception:
        ops_snapshot_refresh_errors_total.inc()
        logger.warning("ops scheduler stats served in degraded mode (redis unavailable)")
    return _add_snapshot_meta_fields(payload, cache_key=cache_key, generated_at=generated_at, stale=False)


async def _compute_ops_scheduler_stats_payload(
    *,
    db: AsyncSession,
) -> dict[str, Any]:
    from sqlalchemy import select, func

    now_utc = datetime.now(timezone.utc)
    day_ago = now_utc - timedelta(hours=24)
    next_hour = now_utc + timedelta(hours=1)
    history_days = 14
    future_days = 7

    active_sources = int(
        (
            await db.execute(
                select(func.count(ParsingSource.id)).where(ParsingSource.is_active.is_(True))
            )
        ).scalar()
        or 0
    )
    paused_sources = int(
        (
            await db.execute(
                select(func.count(ParsingSource.id)).where(ParsingSource.is_active.is_(False))
            )
        ).scalar()
        or 0
    )
    scheduler_paused = await _get_scheduler_paused_state(db)

    due_now = int(
        (
            await db.execute(
                select(func.count(ParsingSource.id)).where(
                    ParsingSource.is_active.is_(True),
                    ParsingSource.next_sync_at <= func.now(),
                    ParsingSource.status.in_(("waiting", "error", "broken")),
                )
            )
        ).scalar()
        or 0
    )
    overdue_15m = int(
        (
            await db.execute(
                select(func.count(ParsingSource.id)).where(
                    ParsingSource.is_active.is_(True),
                    ParsingSource.next_sync_at <= now_utc - timedelta(minutes=15),
                    ParsingSource.status.in_(("waiting", "error", "broken")),
                )
            )
        ).scalar()
        or 0
    )
    next_hour_count = int(
        (
            await db.execute(
                select(func.count(ParsingSource.id)).where(
                    ParsingSource.is_active.is_(True),
                    ParsingSource.next_sync_at > func.now(),
                    ParsingSource.next_sync_at <= next_hour,
                )
            )
        ).scalar()
        or 0
    )

    interval_rows = (
        await db.execute(
            select(
                ParsingSource.refresh_interval_hours,
                func.count(ParsingSource.id),
            )
            .where(ParsingSource.is_active.is_(True))
            .group_by(ParsingSource.refresh_interval_hours)
            .order_by(func.count(ParsingSource.id).desc())
            .limit(8)
        )
    ).all()
    intervals = [
        {
            "refresh_interval_hours": int(hours or 0),
            "sources_count": int(count or 0),
        }
        for hours, count in interval_rows
    ]

    upcoming_rows = (
        await db.execute(
            select(ParsingSource)
            .where(ParsingSource.is_active.is_(True))
            .order_by(ParsingSource.next_sync_at.asc(), ParsingSource.priority.desc())
            .limit(30)
        )
    ).scalars().all()
    upcoming = [
        {
            "source_id": int(src.id),
            "site_key": src.site_key,
            "url": src.url,
            "type": src.type,
            "status": src.status,
            "priority": int(src.priority or 0),
            "refresh_interval_hours": int(src.refresh_interval_hours or 0),
            "next_sync_at": _iso(src.next_sync_at),
            "last_synced_at": _iso(src.last_synced_at),
        }
        for src in upcoming_rows
    ]

    run_rows = (
        await db.execute(
            select(
                ParsingRun.status,
                func.count(ParsingRun.id),
                func.sum(ParsingRun.items_new),
                func.sum(ParsingRun.items_scraped),
                func.avg(ParsingRun.duration_seconds),
            )
            .where(ParsingRun.created_at >= day_ago)
            .group_by(ParsingRun.status)
        )
    ).all()
    runs_24h: dict[str, dict] = {}
    for status, count, items_new, items_scraped, avg_duration in run_rows:
        runs_24h[str(status)] = {
            "count": int(count or 0),
            "items_new": int(items_new or 0),
            "items_scraped": int(items_scraped or 0),
            "avg_duration_seconds": float(avg_duration or 0),
        }

    history_from = now_utc - timedelta(days=history_days - 1)
    queued_history_rows = (
        await db.execute(
            select(
                func.date(ParsingRun.created_at).label("date"),
                func.count(ParsingRun.id).label("queued_count"),
            )
            .where(ParsingRun.created_at >= history_from)
            .group_by(func.date(ParsingRun.created_at))
            .order_by(func.date(ParsingRun.created_at).asc())
        )
    ).all()
    queued_history_map = {
        row.date.isoformat(): int(row.queued_count or 0)
        for row in queued_history_rows
        if row.date is not None
    }

    future_until = now_utc + timedelta(days=future_days)
    planned_future_rows = (
        await db.execute(
            select(
                func.date(ParsingSource.next_sync_at).label("date"),
                func.count(ParsingSource.id).label("planned_count"),
            )
            .where(
                ParsingSource.is_active.is_(True),
                ParsingSource.next_sync_at >= now_utc,
                ParsingSource.next_sync_at <= future_until,
            )
            .group_by(func.date(ParsingSource.next_sync_at))
            .order_by(func.date(ParsingSource.next_sync_at).asc())
        )
    ).all()
    planned_future_map = {
        row.date.isoformat(): int(row.planned_count or 0)
        for row in planned_future_rows
        if row.date is not None
    }

    start_day = (now_utc - timedelta(days=history_days - 1)).date()
    end_day = (now_utc + timedelta(days=future_days)).date()
    trend = []
    day_cursor = start_day
    while day_cursor <= end_day:
        day_key = day_cursor.isoformat()
        trend.append(
            {
                "date": day_key,
                "queued_actual": int(queued_history_map.get(day_key, 0)),
                "planned_future": int(planned_future_map.get(day_key, 0)),
            }
        )
        day_cursor = day_cursor + timedelta(days=1)

    return {
        "status": "ok",
        "summary": {
            "active_sources": active_sources,
            "paused_sources": paused_sources,
            "scheduler_paused": scheduler_paused,
            "due_now": due_now,
            "overdue_15m": overdue_15m,
            "scheduled_next_hour": next_hour_count,
        },
        "intervals": intervals,
        "upcoming": upcoming,
        "runs_24h": runs_24h,
        "queue_plan_trend": trend,
        "generated_at": now_utc.isoformat(),
    }


@router.get("/ops/items-trend")
async def get_ops_items_trend(
    granularity: str = Query("day"),
    buckets: Optional[int] = Query(None, ge=1, le=1000),
    days: Optional[int] = Query(None, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    force_fresh: bool = Query(False),
    _=Depends(verify_internal_token),
):
    settings_state = await _get_or_create_ops_runtime_state(db)
    settings_payload = _serialize_ops_runtime_settings(settings_state)["item"]
    snapshot_ttl_ms = int(settings_payload["ops_snapshot_ttl_ms"])
    stale_max_age_ms = int(settings_payload["ops_stale_max_age_ms"])
    aggregator_enabled = bool(settings_payload.get("ops_aggregator_enabled"))
    g = str(granularity or "day").strip().lower()
    default_buckets = {"week": 12, "day": 30, "hour": 72, "minute": 180}
    bucket_count = int(buckets if buckets is not None else default_buckets.get(g, 30))
    if days is not None and g == "day" and buckets is None:
        bucket_count = int(days)
    cache_key = _snapshot_key("items_trend", granularity=g, buckets=bucket_count)
    if not force_fresh:
        cached = await _snapshot_read(redis, cache_key)
        if cached and isinstance(cached.get("payload"), dict):
            stale = _is_snapshot_stale(cached.get("generated_at"), stale_max_age_ms)
            if not stale:
                ops_snapshot_cache_hits_total.inc()
                return _add_snapshot_meta_fields(cached["payload"], cache_key=cache_key, generated_at=cached.get("generated_at"), stale=False)
            if aggregator_enabled:
                ops_snapshot_stale_served_total.inc()
                await _trigger_snapshot_refresh_if_needed(
                    redis=redis,
                    cache_key=cache_key,
                    block="items_trend",
                    ttl_ms=snapshot_ttl_ms,
                    compute_fn=lambda: _compute_ops_items_trend_payload(granularity=granularity, buckets=buckets, days=days, db=db),
                )
                return _add_snapshot_meta_fields(cached["payload"], cache_key=cache_key, generated_at=cached.get("generated_at"), stale=True)
        ops_snapshot_cache_misses_total.inc()

    payload = await _compute_ops_items_trend_payload(granularity=granularity, buckets=buckets, days=days, db=db)
    generated_at = datetime.now(timezone.utc).isoformat()
    try:
        wrapped, changed = await _snapshot_write(
            redis,
            block="items_trend",
            key=cache_key,
            payload=payload,
            ttl_ms=snapshot_ttl_ms,
        )
        generated_at = wrapped.get("generated_at") or generated_at
        if changed:
            meta = await _snapshot_meta_get(redis)
            await _publish_ops_event(
                redis,
                "ops.snapshot.updated",
                {
                    "block": "items_trend",
                    "key": cache_key,
                    "version": meta.get(cache_key, {}).get("version", 0),
                    "generated_at": generated_at,
                },
            )
    except Exception:
        ops_snapshot_refresh_errors_total.inc()
        logger.warning("ops items trend served in degraded mode (redis unavailable)")
    return _add_snapshot_meta_fields(payload, cache_key=cache_key, generated_at=generated_at, stale=False)


async def _compute_ops_items_trend_payload(
    *,
    granularity: str,
    buckets: Optional[int],
    days: Optional[int],
    db: AsyncSession,
) -> dict[str, Any]:
    from sqlalchemy import select, func

    now_utc = datetime.now(timezone.utc)
    g = str(granularity or "day").strip().lower()
    if g not in {"week", "day", "hour", "minute"}:
        raise HTTPException(status_code=400, detail="granularity must be one of: week,day,hour,minute")

    default_buckets = {
        "week": 12,
        "day": 30,
        "hour": 72,
        "minute": 180,
    }
    bucket_count = int(buckets if buckets is not None else default_buckets[g])

    # Backward compatibility for old caller that used days=...
    if days is not None and g == "day" and buckets is None:
        bucket_count = int(days)

    if g == "week":
        step = timedelta(weeks=1)
    elif g == "day":
        step = timedelta(days=1)
    elif g == "hour":
        step = timedelta(hours=1)
    else:
        step = timedelta(minutes=1)

    def bucket_start(dt: datetime) -> datetime:
        dt = dt.astimezone(timezone.utc)
        if g == "week":
            start = datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)
            return start - timedelta(days=start.weekday())
        if g == "day":
            return datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)
        if g == "hour":
            return datetime(dt.year, dt.month, dt.day, dt.hour, tzinfo=timezone.utc)
        return datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute, tzinfo=timezone.utc)

    end_bucket = bucket_start(now_utc)
    start_bucket = end_bucket - step * max(0, bucket_count - 1)

    product_rows = (
        await db.execute(
            select(Product.created_at)
            .where(Product.created_at >= start_bucket)
            .order_by(Product.created_at.asc())
        )
    ).all()
    category_rows = (
        await db.execute(
            select(DiscoveredCategory.created_at)
            .where(DiscoveredCategory.created_at >= start_bucket)
            .order_by(DiscoveredCategory.created_at.asc())
        )
    ).all()

    buckets_map: dict[str, dict] = {}
    cursor = start_bucket
    for _ in range(bucket_count):
        key = cursor.isoformat()
        buckets_map[key] = {
            "date": key,
            "items_scraped": 0,
            "items_new": 0,
            "categories_new": 0,
            "runs_count": 0,
        }
        cursor = cursor + step

    for (created_at,) in product_rows:
        if created_at is None:
            continue
        b = bucket_start(created_at).isoformat()
        if b not in buckets_map:
            continue
        buckets_map[b]["items_scraped"] += 1
        buckets_map[b]["items_new"] += 1

    for (created_at,) in category_rows:
        if created_at is None:
            continue
        b = bucket_start(created_at).isoformat()
        if b not in buckets_map:
            continue
        buckets_map[b]["categories_new"] += 1

    items = list(buckets_map.values())

    total_scraped = sum(int(x["items_scraped"] or 0) for x in items)
    total_new = sum(int(x["items_new"] or 0) for x in items)
    total_runs = sum(int(x["runs_count"] or 0) for x in items)
    total_categories_new = sum(int(x["categories_new"] or 0) for x in items)

    return {
        "status": "ok",
        "granularity": g,
        "buckets": bucket_count,
        "items": items,
        "totals": {
            "items_scraped": total_scraped,
            "items_new": total_new,
            "categories_new": total_categories_new,
            "runs_count": total_runs,
        },
        "generated_at": now_utc.isoformat(),
    }


@router.get("/ops/sources/{source_id:int}/items-trend")
async def get_ops_source_items_trend(
    source_id: int,
    granularity: str = Query("day"),
    buckets: Optional[int] = Query(None, ge=1, le=1000),
    days: Optional[int] = Query(None, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_internal_token),
):
    from sqlalchemy import select, func

    source = (
        await db.execute(select(ParsingSource).where(ParsingSource.id == source_id))
    ).scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    now_utc = datetime.now(timezone.utc)
    g = str(granularity or "day").strip().lower()
    if g not in {"week", "day", "hour", "minute"}:
        raise HTTPException(status_code=400, detail="granularity must be one of: week,day,hour,minute")

    default_buckets = {
        "week": 12,
        "day": 30,
        "hour": 72,
        "minute": 180,
    }
    bucket_count = int(buckets if buckets is not None else default_buckets[g])
    if days is not None and g == "day" and buckets is None:
        bucket_count = int(days)

    if g == "week":
        step = timedelta(weeks=1)
    elif g == "day":
        step = timedelta(days=1)
    elif g == "hour":
        step = timedelta(hours=1)
    else:
        step = timedelta(minutes=1)

    def bucket_start(dt: datetime) -> datetime:
        dt = dt.astimezone(timezone.utc)
        if g == "week":
            start = datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)
            return start - timedelta(days=start.weekday())
        if g == "day":
            return datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)
        if g == "hour":
            return datetime(dt.year, dt.month, dt.day, dt.hour, tzinfo=timezone.utc)
        return datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute, tzinfo=timezone.utc)

    end_bucket = bucket_start(now_utc)
    start_bucket = end_bucket - step * max(0, bucket_count - 1)

    site_key_expr = func.split_part(Product.product_id, ":", 1)
    filters = [Product.created_at >= start_bucket, site_key_expr == source.site_key]
    if source.type == "list":
        cat_name = str((source.config or {}).get("discovery_name") or "").strip()
        if cat_name:
            filters.append(Product.category == cat_name)

    product_rows = (
        await db.execute(
            select(Product.created_at)
            .where(*filters)
            .order_by(Product.created_at.asc())
        )
    ).all()

    buckets_map: dict[str, dict] = {}
    cursor = start_bucket
    for _ in range(bucket_count):
        key = cursor.isoformat()
        buckets_map[key] = {
            "date": key,
            "items_scraped": 0,
            "items_new": 0,
            "categories_new": 0,
            "runs_count": 0,
        }
        cursor = cursor + step

    for (created_at,) in product_rows:
        if created_at is None:
            continue
        b = bucket_start(created_at).isoformat()
        if b not in buckets_map:
            continue
        buckets_map[b]["items_scraped"] += 1
        buckets_map[b]["items_new"] += 1

    items = list(buckets_map.values())
    total_new = sum(int(x["items_new"] or 0) for x in items)

    return {
        "status": "ok",
        "source_id": int(source_id),
        "site_key": source.site_key,
        "granularity": g,
        "buckets": bucket_count,
        "items": items,
        "totals": {
            "items_scraped": total_new,
            "items_new": total_new,
            "categories_new": 0,
            "runs_count": 0,
        },
        "generated_at": now_utc.isoformat(),
    }


@router.get("/ops/sites")
async def get_ops_sites(
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_internal_token),
):
    from sqlalchemy import select, func

    await _maybe_reconcile_queued_runs_with_rabbit(db)
    rabbit_tasks = await _fetch_rabbit_queued_tasks(limit=2000)
    rabbit_queued_by_site: dict[str, int] = {}
    for task in rabbit_tasks:
        site = str(task.get("site_key") or "").strip()
        if not site:
            continue
        rabbit_queued_by_site[site] = rabbit_queued_by_site.get(site, 0) + 1

    hubs = (await db.execute(select(ParsingHub).order_by(ParsingHub.site_key.asc()))).scalars().all()

    src_rows = (
        await db.execute(
            select(
                ParsingSource.site_key,
                ParsingSource.status,
                func.count(ParsingSource.id),
            ).group_by(ParsingSource.site_key, ParsingSource.status)
        )
    ).all()

    disc_rows = (
        await db.execute(
            select(
                DiscoveredCategory.site_key,
                DiscoveredCategory.state,
                func.count(DiscoveredCategory.id),
            ).group_by(DiscoveredCategory.site_key, DiscoveredCategory.state)
        )
    ).all()
    site_key_expr = func.split_part(Product.product_id, ":", 1)
    product_rows = (
        await db.execute(
            select(
                site_key_expr.label("site_key"),
                func.count(Product.product_id),
            ).group_by(site_key_expr)
        )
    ).all()

    src_counts = {}
    for site_key, status, count in src_rows:
        src_counts.setdefault(site_key, {})[status] = int(count)

    hub_rows = (
        await db.execute(
            select(
                ParsingSource.site_key,
                ParsingSource.id,
                ParsingSource.status,
                ParsingSource.is_active,
                ParsingSource.url,
                ParsingSource.config,
            )
            .where(ParsingSource.type == "hub")
            .order_by(ParsingSource.id.asc())
        )
    ).all()
    hub_map = {}
    for site_key, source_id, status, is_active, source_url, source_config in hub_rows:
        if site_key in hub_map:
            continue
        cfg = source_config or {}
        display_name = _extract_site_name_from_config(cfg)
        hub_map[site_key] = {
            "source_id": int(source_id),
            "status": status,
            "is_active": bool(is_active),
            "url": source_url,
            "name": display_name,
        }

    disc_counts = {}
    for site_key, state, count in disc_rows:
        disc_counts.setdefault(site_key, {})[state] = int(count)
    product_counts = {str(site_key): int(count or 0) for site_key, count in product_rows if site_key}

    items = []
    for hub in hubs:
        counts = src_counts.get(hub.site_key, {})
        dcounts = disc_counts.get(hub.site_key, {})
        runtime_hub = hub_map.get(hub.site_key, {})
        display_name = hub.name or runtime_hub.get("name") or hub.site_key
        display_url = hub.url or runtime_hub.get("url")
        display_status = hub.status or runtime_hub.get("status")
        items.append({
            "site_key": hub.site_key,
            "name": display_name,
            "url": display_url,
            "status": display_status,
            "is_active": hub.is_active,
            "last_synced_at": _iso(hub.last_synced_at),
            "runtime_hub_source_id": runtime_hub.get("source_id"),
            "runtime_hub_status": runtime_hub.get("status"),
            "runtime_hub_is_active": runtime_hub.get("is_active"),
            "counters": {
                "discovered_new": dcounts.get("new", 0),
                "discovered_promoted": dcounts.get("promoted", 0),
                "discovered_rejected": dcounts.get("rejected", 0),
                "discovered_inactive": dcounts.get("inactive", 0),
                "discovered_total": (
                    dcounts.get("new", 0)
                    + dcounts.get("promoted", 0)
                    + dcounts.get("rejected", 0)
                    + dcounts.get("inactive", 0)
                ),
                "products_total": product_counts.get(hub.site_key, 0),
                "queued": rabbit_queued_by_site.get(hub.site_key, 0),
                "running": counts.get("running", 0),
                "error": counts.get("error", 0),
                "waiting": counts.get("waiting", 0),
                "broken": counts.get("broken", 0),
            },
        })

    return {"status": "ok", "items": items}


@router.get("/ops/sites/{site_key}/pipeline")
async def get_ops_site_pipeline(
    site_key: str,
    lane_limit: int = Query(120, ge=10, le=500),
    lane_offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_internal_token),
):
    from sqlalchemy import select

    await _maybe_reconcile_queued_runs_with_rabbit(db)
    rabbit_tasks = await _fetch_rabbit_queued_tasks(limit=2000)

    categories = (
        await db.execute(
            select(DiscoveredCategory)
            .where(DiscoveredCategory.site_key == site_key)
            .order_by(DiscoveredCategory.created_at.desc())
            .limit(10000)
        )
    ).scalars().all()

    list_sources = (
        await db.execute(
            select(ParsingSource)
            .where(ParsingSource.site_key == site_key, ParsingSource.type == "list")
            .order_by(ParsingSource.updated_at.desc())
            .limit(10000)
        )
    ).scalars().all()

    runs = (
        await db.execute(
            select(ParsingRun, ParsingSource)
            .join(ParsingSource, ParsingRun.source_id == ParsingSource.id)
            .where(ParsingSource.site_key == site_key)
            .order_by(ParsingRun.created_at.desc())
            .limit(15000)
        )
    ).all()

    lanes = {
        "discovered:new": [],
        "discovered:promoted": [],
        "queued": [],
        "running": [],
        "completed": [],
        "error": [],
    }

    for cat in categories:
        card = {
            "type": "category",
            "id": cat.id,
            "site_key": cat.site_key,
            "name": cat.name,
            "url": cat.url,
            "state": cat.state,
            "promoted_source_id": cat.promoted_source_id,
            "created_at": _iso(cat.created_at),
        }
        if cat.state == "new":
            lanes["discovered:new"].append(card)
        elif cat.state == "promoted":
            lanes["discovered:promoted"].append(card)

    for src in list_sources:
        card = {
            "type": "source",
            "id": src.id,
            "site_key": src.site_key,
            "url": src.url,
            "status": src.status,
            "is_active": src.is_active,
            "priority": src.priority,
            "refresh_interval_hours": src.refresh_interval_hours,
            "category_id": src.category_id,
            "name": (src.config or {}).get("discovery_name"),
            "updated_at": _iso(src.updated_at),
        }
        if src.status == "running":
            lanes["running"].append(card)
        elif src.status == "error":
            lanes["error"].append(card)

    for idx, task in enumerate(rabbit_tasks):
        task_site = str(task.get("site_key") or "").strip()
        if task_site != site_key:
            continue
        source_id = task.get("source_id")
        queued_card = {
            "type": "source",
            "id": int(source_id) if isinstance(source_id, int) else None,
            "source_id": int(source_id) if isinstance(source_id, int) else None,
            "site_key": task_site,
            "url": task.get("url"),
            "status": "queued",
            "name": ((task.get("config") or {}).get("discovery_name") if isinstance(task.get("config"), dict) else None),
            "updated_at": _iso(datetime.now(timezone.utc)),
            "task_index": idx,
        }
        lanes["queued"].append(queued_card)

    for run, src in runs:
        card = {
            "type": "run",
            "id": run.id,
            "run_id": run.id,
            "source_id": run.source_id,
            "site_key": src.site_key,
            "name": (src.config or {}).get("discovery_name") if src else None,
            "status": run.status,
            "items_scraped": run.items_scraped,
            "items_new": run.items_new,
            "error_message": run.error_message,
            "created_at": _iso(run.created_at),
            "updated_at": _iso(run.updated_at),
        }
        if run.status == "completed":
            lanes["completed"].append(card)
        elif run.status == "error":
            lanes["error"].append(card)
        elif run.status == "running":
            lanes["running"].append(card)

    lane_totals = {key: len(items) for key, items in lanes.items()}
    for key in lanes:
        lanes[key] = lanes[key][lane_offset: lane_offset + lane_limit]

    return {
        "status": "ok",
        "site_key": site_key,
        "lanes": lanes,
        "lane_totals": lane_totals,
        "lane_limit": lane_limit,
        "lane_offset": lane_offset,
    }


@router.get("/ops/runs/active")
async def get_ops_active_runs(
    limit: int = 200,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_internal_token),
):
    from sqlalchemy import select

    await _maybe_reconcile_queued_runs_with_rabbit(db)
    safe_limit = max(1, min(limit, 1000))
    rabbit_tasks = await _fetch_rabbit_queued_tasks(limit=safe_limit)

    running_rows = (
        await db.execute(
            select(ParsingSource)
            .where(ParsingSource.status == "running")
            .order_by(ParsingSource.updated_at.desc())
            .limit(safe_limit)
        )
    ).scalars().all()

    items = []
    # Queue is sourced exclusively from RabbitMQ.
    for idx, task in enumerate(rabbit_tasks):
        source_id = task.get("source_id")
        run_id = task.get("run_id")
        task_type = task.get("type")
        task_source_name = ((task.get("config") or {}).get("discovery_name") if isinstance(task.get("config"), dict) else None)
        items.append({
            "run_id": int(run_id) if isinstance(run_id, int) else 2_000_000_000 + idx,
            "source_id": int(source_id) if isinstance(source_id, int) else None,
            "site_key": task.get("site_key"),
            "source_name": task_source_name,
            "source_type": task_type,
            "category_name": task_source_name if task_type == "list" else None,
            "source_url": task.get("url"),
            "status": "queued",
            "items_scraped": 0,
            "categories_scraped": 0,
            "items_new": 0,
            "created_at": _iso(datetime.now(timezone.utc)),
            "updated_at": _iso(datetime.now(timezone.utc)),
        })

    for src in running_rows:
        source_name = (src.config or {}).get("discovery_name")
        items.append({
            "run_id": 1_000_000_000 + int(src.id),
            "source_id": int(src.id),
            "site_key": src.site_key,
            "source_name": source_name,
            "source_type": src.type,
            "category_name": source_name if src.type == "list" else None,
            "source_url": src.url,
            "status": "running",
            "items_scraped": 0,
            "categories_scraped": 0,
            "items_new": 0,
            "created_at": _iso(src.updated_at),
            "updated_at": _iso(src.updated_at),
        })
    return {"status": "ok", "items": items[:safe_limit]}


@router.get("/ops/runs/queued")
async def get_ops_queued_runs(
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_internal_token),
):
    safe_limit = max(1, min(limit, 200))
    safe_offset = max(0, int(offset))

    queue_stats = await _fetch_rabbit_queue_stats()
    total = int(queue_stats.get("messages_total", 0) or 0) if queue_stats.get("status") == "ok" else 0

    fetch_count = min(10000, safe_offset + safe_limit)
    rabbit_tasks = await _fetch_rabbit_queued_tasks(limit=max(fetch_count, safe_limit))
    page_tasks = rabbit_tasks[safe_offset : safe_offset + safe_limit]

    now_iso = _iso(datetime.now(timezone.utc))
    items = []
    for idx, task in enumerate(page_tasks):
        source_id = task.get("source_id")
        run_id = task.get("run_id")
        task_type = task.get("type")
        task_source_name = ((task.get("config") or {}).get("discovery_name") if isinstance(task.get("config"), dict) else None)
        absolute_idx = safe_offset + idx
        items.append(
            {
                "run_id": int(run_id) if isinstance(run_id, int) else 2_000_000_000 + absolute_idx,
                "source_id": int(source_id) if isinstance(source_id, int) else None,
                "site_key": task.get("site_key"),
                "source_name": task_source_name,
                "source_type": task_type,
                "category_name": task_source_name if task_type == "list" else None,
                "source_url": task.get("url"),
                "status": "queued",
                "items_scraped": 0,
                "categories_scraped": 0,
                "items_new": 0,
                "created_at": now_iso,
                "updated_at": now_iso,
            }
        )

    return {
        "status": "ok",
        "total": total,
        "limit": safe_limit,
        "offset": safe_offset,
        "count": len(items),
        "items": items,
    }


@router.get("/ops/runs/{run_id}")
async def get_ops_run_details(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_internal_token),
):
    from sqlalchemy import select
    from app.models import DiscoveredCategory

    row = (
        await db.execute(
            select(ParsingRun, ParsingSource, DiscoveredCategory)
            .join(ParsingSource, ParsingRun.source_id == ParsingSource.id)
            .outerjoin(DiscoveredCategory, ParsingSource.category_id == DiscoveredCategory.id)
            .where(ParsingRun.id == run_id)
        )
    ).first()
    if not row:
        # Synthetic active-run ids (non-persisted queued/running) fallback.
        synthetic_running_prefix = 1_000_000_000
        synthetic_queued_prefix = 2_000_000_000
        if run_id >= synthetic_running_prefix:
            if run_id >= synthetic_queued_prefix:
                task_idx = run_id - synthetic_queued_prefix
                if task_idx < 0:
                    raise HTTPException(status_code=404, detail="Run not found")
                rabbit_tasks = await _fetch_rabbit_queued_tasks(limit=max(50, task_idx + 1))
                if task_idx >= len(rabbit_tasks):
                    raise HTTPException(status_code=404, detail="Run not found")
                task = rabbit_tasks[task_idx]
                task_type = task.get("type")
                task_source_name = ((task.get("config") or {}).get("discovery_name") if isinstance(task.get("config"), dict) else None)
                return {
                    "status": "ok",
                    "item": {
                        "run_id": run_id,
                        "source_id": task.get("source_id"),
                        "site_key": task.get("site_key"),
                        "source_url": task.get("url"),
                        "source_type": task_type,
                        "source_name": task_source_name,
                        "category_name": task_source_name if task_type == "list" else None,
                        "run_status": "queued",
                        "items_scraped": 0,
                        "categories_scraped": 0,
                        "items_new": 0,
                        "error_message": None,
                        "duration_seconds": None,
                        "created_at": _iso(datetime.now(timezone.utc)),
                        "updated_at": _iso(datetime.now(timezone.utc)),
                        "logs": "",
                        "logs_meta": {"chars": 0, "lines": 0},
                        "timeline": [
                            {"status": "queued", "at": _iso(datetime.now(timezone.utc))}
                        ],
                    },
                }
            source_id = run_id - synthetic_running_prefix
            src = (
                await db.execute(select(ParsingSource).where(ParsingSource.id == source_id))
            ).scalar_one_or_none()
            if not src:
                raise HTTPException(status_code=404, detail="Run not found")
            return {
                "status": "ok",
                "item": {
                    "run_id": run_id,
                    "source_id": src.id,
                    "site_key": src.site_key,
                    "source_url": src.url,
                    "source_type": src.type,
                    "source_name": (src.config or {}).get("discovery_name"),
                    "category_name": ((src.config or {}).get("discovery_name") if src.type == "list" else None),
                    "run_status": "running",
                    "items_scraped": 0,
                    "categories_scraped": 0,
                    "items_new": 0,
                    "error_message": None,
                    "duration_seconds": None,
                    "created_at": _iso(src.updated_at),
                    "updated_at": _iso(src.updated_at),
                    "logs": (src.config or {}).get("last_logs", ""),
                    "logs_meta": {
                        "chars": len((src.config or {}).get("last_logs", "") or ""),
                        "lines": len(((src.config or {}).get("last_logs", "") or "").splitlines()),
                    },
                    "timeline": [
                        {"status": "running", "at": _iso(src.updated_at)},
                    ],
                },
            }
        raise HTTPException(status_code=404, detail="Run not found")
    run, source, category = row

    if run.duration_seconds is not None:
        duration = float(run.duration_seconds)
    elif run.created_at and run.updated_at:
        duration = max((run.updated_at - run.created_at).total_seconds(), 0.0)
    else:
        duration = None

    timeline = [
        {
            "status": "queued",
            "at": _iso(run.created_at),
        }
    ]
    if run.status in {"running", "completed", "error"}:
        timeline.append(
            {
                "status": "running",
                "at": _iso(run.updated_at if run.status == "running" else run.created_at),
            }
        )
    if run.status in {"completed", "error"}:
        timeline.append(
            {
                "status": run.status,
                "at": _iso(run.updated_at),
            }
        )

    logs_text = run.logs or ""
    logs_lines = len(logs_text.splitlines()) if logs_text else 0
    categories_scraped = _extract_categories_scraped_from_logs(logs_text)
    category_name = None
    if source.type == "list":
        category_name = (category.name if category else None) or ((source.config or {}).get("discovery_name"))

    return {
        "status": "ok",
        "item": {
            "run_id": run.id,
            "source_id": run.source_id,
            "site_key": source.site_key,
            "source_url": source.url,
            "source_type": source.type,
            "source_name": (source.config or {}).get("discovery_name"),
            "category_name": category_name,
            "run_status": run.status,
            "items_scraped": run.items_scraped,
            "categories_scraped": categories_scraped,
            "items_new": run.items_new,
            "error_message": run.error_message,
            "duration_seconds": duration,
            "created_at": _iso(run.created_at),
            "updated_at": _iso(run.updated_at),
            "logs": logs_text,
            "logs_meta": {
                "chars": len(logs_text),
                "lines": logs_lines,
            },
            "timeline": timeline,
        },
    }


@router.post("/ops/runs/{run_id}/retry")
async def retry_ops_run(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    _=Depends(verify_internal_token),
):
    from sqlalchemy import select
    from app.utils.rabbitmq import publish_parsing_task

    row = (
        await db.execute(
            select(ParsingRun, ParsingSource)
            .join(ParsingSource, ParsingRun.source_id == ParsingSource.id)
            .where(ParsingRun.id == run_id)
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    _, source = row

    repo = ParsingRepository(db)
    task = {
        "source_id": source.id,
        "url": source.url,
        "site_key": source.site_key,
        "type": source.type,
        "strategy": source.strategy,
        "config": source.config,
    }
    success = publish_parsing_task(task)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to publish retry task")
    await repo.set_queued(source.id)
    await _publish_ops_event(
        redis,
        "run.status_changed",
        {
            "run_id": None,
            "source_id": int(source.id),
            "site_key": source.site_key,
            "from": None,
            "to": "queued",
            "ts": datetime.now(timezone.utc).isoformat(),
        },
    )
    queue_stats = await _fetch_rabbit_queue_stats()
    if queue_stats.get("status") == "ok":
        await _publish_ops_event(
            redis,
            "queue.updated",
            {**queue_stats, "ts": datetime.now(timezone.utc).isoformat()},
        )
    return {"status": "ok", "queued": True}


@router.get("/ops/discovery/categories")
async def get_ops_discovery_categories(
    state: Optional[str] = Query(None),
    site_key: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_internal_token),
):
    from sqlalchemy import select, or_, func

    stmt = select(DiscoveredCategory)
    if state:
        states = [s.strip() for s in state.split(",") if s.strip()]
        if states:
            stmt = stmt.where(DiscoveredCategory.state.in_(states))
    if site_key:
        stmt = stmt.where(DiscoveredCategory.site_key == site_key)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            or_(
                DiscoveredCategory.name.ilike(pattern),
                DiscoveredCategory.url.ilike(pattern),
                DiscoveredCategory.site_key.ilike(pattern),
            )
        )
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = int((await db.execute(count_stmt)).scalar() or 0)

    products_subq = (
        select(
            ProductCategoryLink.discovered_category_id.label("category_id"),
            func.count(ProductCategoryLink.product_id).label("products_total"),
        )
        .group_by(ProductCategoryLink.discovered_category_id)
        .subquery()
    )
    last_run_subq = (
        select(
            ParsingSource.category_id.label("category_id"),
            func.max(ParsingRun.updated_at).label("last_run_at"),
        )
        .join(ParsingRun, ParsingRun.source_id == ParsingSource.id)
        .where(ParsingSource.category_id.is_not(None))
        .group_by(ParsingSource.category_id)
        .subquery()
    )

    stmt = (
        select(
            DiscoveredCategory,
            func.coalesce(products_subq.c.products_total, 0).label("products_total"),
            last_run_subq.c.last_run_at.label("last_run_at"),
        )
        .outerjoin(
            products_subq,
            products_subq.c.category_id == DiscoveredCategory.id,
        )
        .outerjoin(last_run_subq, last_run_subq.c.category_id == DiscoveredCategory.id)
    )
    if state:
        states = [s.strip() for s in state.split(",") if s.strip()]
        if states:
            stmt = stmt.where(DiscoveredCategory.state.in_(states))
    if site_key:
        stmt = stmt.where(DiscoveredCategory.site_key == site_key)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            or_(
                DiscoveredCategory.name.ilike(pattern),
                DiscoveredCategory.url.ilike(pattern),
                DiscoveredCategory.site_key.ilike(pattern),
            )
        )
    stmt = stmt.order_by(DiscoveredCategory.created_at.desc()).offset(offset).limit(limit)
    rows = (await db.execute(stmt)).all()

    items = [
        {
            "id": c.id,
            "hub_id": c.hub_id,
            "site_key": c.site_key,
            "url": c.url,
            "name": c.name,
            "parent_url": c.parent_url,
            "state": c.state,
            "promoted_source_id": c.promoted_source_id,
            "created_at": _iso(c.created_at),
            "updated_at": _iso(c.updated_at),
            "products_total": int(products_total or 0),
            "last_run_at": _iso(last_run_at),
        }
        for c, products_total, last_run_at in rows
    ]
    return {"status": "ok", "items": items, "total": total}


@router.get("/ops/discovery/categories/{category_id}")
async def get_ops_discovery_category_details(
    category_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_internal_token),
):
    from sqlalchemy import select, func

    category = (
        await db.execute(select(DiscoveredCategory).where(DiscoveredCategory.id == category_id))
    ).scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    products_total = 0
    products_total = int(
        (
            await db.execute(
                select(func.count(ProductCategoryLink.product_id)).where(
                    ProductCategoryLink.discovered_category_id == category.id
                )
            )
        ).scalar()
        or 0
    )

    source = None
    if category.promoted_source_id:
        source = (
            await db.execute(
                select(ParsingSource).where(ParsingSource.id == category.promoted_source_id)
            )
        ).scalar_one_or_none()

    runs: list[ParsingRun] = []
    trend: list[dict] = []
    if source:
        runs = (
            await db.execute(
                select(ParsingRun)
                .where(ParsingRun.source_id == source.id)
                .order_by(ParsingRun.created_at.desc())
                .limit(30)
            )
        ).scalars().all()

        trend_rows = (
            await db.execute(
                select(
                    func.date(ParsingRun.updated_at).label("date"),
                    func.sum(ParsingRun.items_new).label("items_new"),
                    func.sum(ParsingRun.items_scraped).label("items_scraped"),
                )
                .where(ParsingRun.source_id == source.id)
                .group_by(func.date(ParsingRun.updated_at))
                .order_by(func.date(ParsingRun.updated_at).desc())
                .limit(21)
            )
        ).all()
        trend = [
            {
                "date": row.date.isoformat() if row.date else None,
                "items_new": int(row.items_new or 0),
                "items_scraped": int(row.items_scraped or 0),
            }
            for row in reversed(trend_rows)
            if row.date is not None
        ]

    last_run = runs[0] if runs else None
    run_items = [
        {
            "id": int(run.id),
            "status": run.status,
            "items_new": int(run.items_new or 0),
            "items_scraped": int(run.items_scraped or 0),
            "error_message": run.error_message,
            "duration_seconds": run.duration_seconds,
            "created_at": _iso(run.created_at),
            "updated_at": _iso(run.updated_at),
        }
        for run in runs
    ]

    return {
        "status": "ok",
        "item": {
            "id": category.id,
            "hub_id": category.hub_id,
            "site_key": category.site_key,
            "name": category.name,
            "url": category.url,
            "parent_url": category.parent_url,
            "state": category.state,
            "promoted_source_id": category.promoted_source_id,
            "created_at": _iso(category.created_at),
            "updated_at": _iso(category.updated_at),
            "products_total": products_total,
            "last_run_at": _iso(last_run.updated_at if last_run else None),
            "last_run_status": (last_run.status if last_run else None),
            "last_run_new": int(last_run.items_new or 0) if last_run else 0,
            "last_run_scraped": int(last_run.items_scraped or 0) if last_run else 0,
            "runtime_source": (
                {
                    "id": int(source.id),
                    "status": source.status,
                    "is_active": bool(source.is_active),
                    "priority": int(source.priority or 0),
                    "refresh_interval_hours": int(source.refresh_interval_hours or 0),
                    "last_synced_at": _iso(source.last_synced_at),
                }
                if source
                else None
            ),
            "trend": trend,
            "recent_runs": run_items,
        },
    }


@router.post("/ops/discovery/promote")
async def promote_ops_discovery_categories(
    category_ids: List[int] = Body(default_factory=list, embed=True),
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_internal_token),
):
    repo = ParsingRepository(db)
    activated_count = await repo.activate_sources(category_ids)
    return {"status": "ok", "activated_count": activated_count}


@router.post("/ops/discovery/reject")
async def reject_ops_discovery_categories(
    category_ids: List[int] = Body(default_factory=list, embed=True),
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_internal_token),
):
    from sqlalchemy import update

    if not category_ids:
        return {"status": "ok", "updated": 0}
    stmt = (
        update(DiscoveredCategory)
        .where(DiscoveredCategory.id.in_(category_ids))
        .values(state="rejected")
    )
    res = await db.execute(stmt)
    await db.commit()
    return {"status": "ok", "updated": int(res.rowcount or 0)}


@router.post("/ops/discovery/reactivate")
async def reactivate_ops_discovery_categories(
    category_ids: List[int] = Body(default_factory=list, embed=True),
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_internal_token),
):
    from sqlalchemy import update

    if not category_ids:
        return {"status": "ok", "updated": 0}
    stmt = (
        update(DiscoveredCategory)
        .where(DiscoveredCategory.id.in_(category_ids))
        .values(state="new")
    )
    res = await db.execute(stmt)
    await db.commit()
    return {"status": "ok", "updated": int(res.rowcount or 0)}


@router.post("/ops/discovery/categories/{category_id}/run-now")
async def run_ops_discovery_category_now(
    category_id: int,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    _=Depends(verify_internal_token),
):
    from sqlalchemy import select
    from app.utils.rabbitmq import publish_parsing_task

    category = (
        await db.execute(
            select(DiscoveredCategory).where(DiscoveredCategory.id == category_id)
        )
    ).scalar_one_or_none()
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")

    if category.state != "promoted" or not category.promoted_source_id:
        raise HTTPException(status_code=409, detail="Category is not approved yet. Approve category before run.")

    repo = ParsingRepository(db)
    source = (
        await db.execute(
            select(ParsingSource).where(ParsingSource.id == category.promoted_source_id)
        )
    ).scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=409, detail="Approved category has no runtime source. Re-approve category.")

    source.is_active = True
    source.status = "waiting"
    cfg = dict(source.config or {})
    if category.name and not cfg.get("discovery_name"):
        cfg["discovery_name"] = category.name
    if category.parent_url and not cfg.get("parent_url"):
        cfg["parent_url"] = category.parent_url
    cfg["discovered_category_id"] = category.id
    source.config = cfg
    await db.commit()
    await db.refresh(source)

    task = {
        "source_id": int(source.id),
        "url": source.url,
        "site_key": source.site_key,
        "type": source.type,
        "strategy": source.strategy or "deep",
        "config": source.config or {},
    }
    success = publish_parsing_task(task)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to queue category task")

    await repo.set_queued(source.id)
    await _publish_ops_event(
        redis,
        "run.status_changed",
        {
            "run_id": None,
            "source_id": int(source.id),
            "site_key": source.site_key,
            "from": None,
            "to": "queued",
            "ts": datetime.now(timezone.utc).isoformat(),
        },
    )
    queue_stats = await _fetch_rabbit_queue_stats()
    if queue_stats.get("status") == "ok":
        await _publish_ops_event(
            redis,
            "queue.updated",
            {**queue_stats, "ts": datetime.now(timezone.utc).isoformat()},
        )
    return {
        "status": "ok",
        "queued": True,
        "category_id": int(category.id),
        "source_id": int(source.id),
        "site_key": source.site_key,
    }


@router.post("/ops/discovery/run-all")
async def run_ops_discovery_all_categories(
    payload: dict = Body(default={}),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    _=Depends(verify_internal_token),
):
    from sqlalchemy import select
    from app.utils.rabbitmq import publish_parsing_task

    site_key = str(payload.get("site_key") or "").strip()
    if not site_key:
        raise HTTPException(status_code=400, detail="site_key is required")

    limit = int(payload.get("limit") or 5000)
    limit = max(1, min(limit, 10000))

    raw_states = payload.get("states")
    if isinstance(raw_states, list) and raw_states:
        allowed_states = {"promoted"}
        states = [str(s).strip().lower() for s in raw_states if str(s).strip().lower() in allowed_states]
        if not states:
            states = ["promoted"]
    else:
        states = ["promoted"]

    q = str(payload.get("q") or "").strip().lower()

    stmt = (
        select(DiscoveredCategory)
        .where(
            DiscoveredCategory.site_key == site_key,
            DiscoveredCategory.state.in_(states),
        )
        .order_by(DiscoveredCategory.updated_at.desc())
        .limit(limit)
    )
    cats = (await db.execute(stmt)).scalars().all()
    if q:
        cats = [
            c for c in cats
            if q in str(c.name or "").lower() or q in str(c.url or "").lower()
        ]
    if not cats:
        return {
            "status": "ok",
            "site_key": site_key,
            "selected": 0,
            "queued": 0,
            "skipped": 0,
            "failed": 0,
            "details": [],
        }

    repo = ParsingRepository(db)

    rabbit_probe_limit = min(10000, max(2000, len(cats) * 2))
    _, rabbit_queued_source_ids = await _fetch_rabbit_queued_task_ids(limit=rabbit_probe_limit)

    running_source_ids = set(
        (
            await db.execute(
                select(ParsingSource.id).where(
                    ParsingSource.site_key == site_key,
                    ParsingSource.status == "running",
                )
            )
        ).scalars().all()
    )

    promoted_source_ids = {int(c.promoted_source_id) for c in cats if c.promoted_source_id}
    promoted_sources = {}
    if promoted_source_ids:
        rows = (
            await db.execute(
                select(ParsingSource).where(ParsingSource.id.in_(promoted_source_ids))
            )
        ).scalars().all()
        promoted_sources = {int(s.id): s for s in rows}

    selected = 0
    queued = 0
    skipped = 0
    failed = 0
    details = []

    for cat in cats:
        selected += 1
        source = promoted_sources.get(int(cat.promoted_source_id)) if cat.promoted_source_id else None
        if source is None:
            skipped += 1
            details.append({"category_id": int(cat.id), "status": "skipped", "reason": "not_approved"})
            continue

        sid = int(source.id)
        if sid in rabbit_queued_source_ids or sid in running_source_ids or source.status in {"queued", "running"}:
            skipped += 1
            details.append({"category_id": int(cat.id), "source_id": sid, "status": "skipped", "reason": "already_queued_or_running"})
            continue

        source.is_active = True
        source.status = "waiting"
        cfg = dict(source.config or {})
        cfg["discovered_category_id"] = int(cat.id)
        if cat.name and not cfg.get("discovery_name"):
            cfg["discovery_name"] = cat.name
        if cat.parent_url and not cfg.get("parent_url"):
            cfg["parent_url"] = cat.parent_url
        source.config = cfg
        cat.state = "promoted"
        cat.promoted_source_id = sid

        task = {
            "source_id": sid,
            "url": source.url,
            "site_key": source.site_key,
            "type": source.type,
            "strategy": source.strategy or "deep",
            "config": source.config or {},
        }
        success = publish_parsing_task(task)
        if not success:
            failed += 1
            details.append({"category_id": int(cat.id), "source_id": sid, "status": "failed", "reason": "publish_failed"})
            continue

        await repo.set_queued(sid)
        rabbit_queued_source_ids.add(sid)
        queued += 1
        details.append({"category_id": int(cat.id), "source_id": sid, "status": "queued"})

    await db.commit()

    queue_stats = await _fetch_rabbit_queue_stats()
    if queue_stats.get("status") == "ok":
        await _publish_ops_event(
            redis,
            "queue.updated",
            {**queue_stats, "ts": datetime.now(timezone.utc).isoformat()},
        )

    return {
        "status": "ok",
        "site_key": site_key,
        "selected": selected,
        "queued": queued,
        "skipped": skipped,
        "failed": failed,
        "details": details[:200],
    }


@router.post("/ops/sources/bulk-update")
async def bulk_update_ops_sources(
    payload: dict = Body(default={}),
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_internal_token),
):
    from sqlalchemy import update

    source_ids = payload.get("source_ids") or []
    if not source_ids:
        return {"status": "ok", "updated": 0}

    updates = {}
    if "priority" in payload:
        updates["priority"] = int(payload["priority"])
    if "refresh_interval_hours" in payload:
        updates["refresh_interval_hours"] = int(payload["refresh_interval_hours"])
    if "is_active" in payload:
        updates["is_active"] = bool(payload["is_active"])
        updates["status"] = "waiting" if bool(payload["is_active"]) else "disabled"
    if not updates:
        return {"status": "ok", "updated": 0}

    stmt = (
        update(ParsingSource)
        .where(ParsingSource.id.in_(source_ids))
        .values(**updates)
    )
    res = await db.execute(stmt)
    await db.commit()
    return {"status": "ok", "updated": int(res.rowcount or 0)}


@router.post("/ops/sites/{site_key}/run-discovery")
async def run_discovery_for_site(
    site_key: str,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    _=Depends(verify_internal_token),
):
    from sqlalchemy import select
    from app.utils.rabbitmq import publish_parsing_task

    hub = (
        await db.execute(
            select(ParsingHub).where(ParsingHub.site_key == site_key)
        )
    ).scalar_one_or_none()
    if hub is None:
        raise HTTPException(status_code=404, detail=f"Discovery hub not found for site '{site_key}'")

    source = (
        await db.execute(
            select(ParsingSource).where(
                ParsingSource.site_key == site_key,
                ParsingSource.type == "hub",
            )
        )
    ).scalar_one_or_none()

    # Keep a lightweight runtime hub source only as execution anchor for parsing_runs.
    # Discovery URL/strategy are sourced from parsing_hubs.
    discovery_url = hub.url
    discovery_strategy = hub.strategy or "discovery"
    merged_config = dict(hub.config or {})
    if source and isinstance(source.config, dict):
        merged_config.update(source.config)

    if source is None:
        source = ParsingSource(
            site_key=site_key,
            url=discovery_url,
            type="hub",
            strategy=discovery_strategy,
            is_active=bool(hub.is_active),
            status="waiting",
            config={**merged_config, "created_by": "ops_run_discovery"},
        )
        db.add(source)
        await db.commit()
        await db.refresh(source)
    else:
        # Align execution anchor with hub settings to avoid divergence.
        source.url = discovery_url
        source.strategy = discovery_strategy
        source.is_active = bool(hub.is_active)
        source.config = merged_config or source.config
        await db.commit()
        await db.refresh(source)

    repo = ParsingRepository(db)
    task = {
        "source_id": source.id,
        "url": discovery_url,
        "site_key": source.site_key,
        "type": source.type,
        "strategy": discovery_strategy,
        "config": merged_config,
    }
    success = publish_parsing_task(task)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to publish discovery task")

    hub.status = "queued"
    hub.next_sync_at = datetime.now() + timedelta(minutes=15)
    await db.commit()
    await repo.set_queued(source.id)
    await _publish_ops_event(
        redis,
        "run.status_changed",
        {
            "run_id": None,
            "source_id": int(source.id),
            "site_key": source.site_key,
            "from": None,
            "to": "queued",
            "ts": datetime.now(timezone.utc).isoformat(),
        },
    )
    queue_stats = await _fetch_rabbit_queue_stats()
    if queue_stats.get("status") == "ok":
        await _publish_ops_event(
            redis,
            "queue.updated",
            {**queue_stats, "ts": datetime.now(timezone.utc).isoformat()},
        )
    return {"status": "ok", "queued": True, "source_id": source.id, "site_key": site_key}


@router.get("/ops/stream")
async def stream_ops_events(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    x_internal_token: Optional[str] = Header(None),
    x_tg_init_data: Optional[str] = Header(None),
    tg_init_data: Optional[str] = Query(None),
    internal_token: Optional[str] = Query(None),
):
    await verify_internal_token(
        x_internal_token=x_internal_token or internal_token,
        x_tg_init_data=x_tg_init_data or tg_init_data,
        db=db,
    )


@router.get("/logs/services", summary="List available log services from Loki")
async def list_log_services(
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token),
):
    client = LokiLogsClient()
    try:
        values = await client.label_values("service")
        # Compose default noise: keep stable order
        values = sorted(set(values))
        if values:
            return {"items": values}
    except Exception as e:
        logger.warning(f"Failed to fetch Loki label values for 'service': {type(e).__name__}: {e}")

    # Fallback: common compose services (works even if labels are missing).
    return {"items": ["api", "scraper", "scheduler", "telegram-bot", "postgres", "redis", "rabbitmq", "loki", "promtail"]}


@router.get("/logs/query", summary="Query recent logs from Loki (history)")
async def query_logs(
    service: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=2000),
    since_seconds: int = Query(300, ge=5, le=24 * 3600),
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token),
):
    client = LokiLogsClient()
    now_ns = int(datetime.now(timezone.utc).timestamp() * 1_000_000_000)
    start_ns = now_ns - int(since_seconds) * 1_000_000_000
    query = build_logql_query(service=service, contains=q)
    try:
        lines = await client.query_range(query=query, start_ns=start_ns, end_ns=now_ns, limit=limit, direction="BACKWARD")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Loki query failed: {type(e).__name__}: {e}")

    items = [
        {
            "ts": line.ts_iso,
            "ts_ns": line.ts_ns,
            "service": line.labels.get("service"),
            "container": line.labels.get("container"),
            "labels": line.labels,
            "line": line.line,
        }
        for line in lines
    ]
    return {"items": items, "query": query}


@router.get("/logs/stream", summary="Stream logs from Loki (tail, SSE)")
async def stream_logs(
    db: AsyncSession = Depends(get_db),
    x_internal_token: Optional[str] = Header(None),
    x_tg_init_data: Optional[str] = Header(None),
    tg_init_data: Optional[str] = Query(None),
    internal_token: Optional[str] = Query(None),
    service: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=2000),
):
    await verify_internal_token(
        x_internal_token=x_internal_token or internal_token,
        x_tg_init_data=x_tg_init_data or tg_init_data,
        db=db,
    )

    loki = LokiLogsClient()
    query = build_logql_query(service=service, contains=q)

    async def event_gen() -> AsyncGenerator[str, None]:
        import time

        last_ping = time.monotonic()
        # Send initial meta event
        yield f"event: logs.meta\ndata: {json.dumps({'query': query, 'service': service, 'ts': datetime.now(timezone.utc).isoformat()}, ensure_ascii=False)}\n\n"

        try:
            async for line in loki.tail(query=query, limit=limit):
                payload = {
                    "ts": line.ts_iso,
                    "ts_ns": line.ts_ns,
                    "service": line.labels.get("service"),
                    "container": line.labels.get("container"),
                    "labels": line.labels,
                    "line": line.line,
                }
                yield f"event: log.line\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

                now = time.monotonic()
                if now - last_ping >= 15:
                    last_ping = now
                    yield f"event: ping\ndata: {json.dumps({'ts': datetime.now(timezone.utc).isoformat()})}\n\n"
        except Exception as e:
            err = {"message": f"{type(e).__name__}: {e}", "ts": datetime.now(timezone.utc).isoformat()}
            yield f"event: logs.error\ndata: {json.dumps(err, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

    async def event_gen() -> AsyncGenerator[str, None]:
        import time

        pubsub = redis.pubsub()
        await pubsub.subscribe(OPS_EVENTS_CHANNEL)
        last_ping = time.monotonic()

        # Send initial queue snapshot on connect.
        queue = await _fetch_rabbit_queue_stats()
        if queue.get("status") == "ok":
            yield f"event: queue.updated\ndata: {json.dumps({**queue, 'ts': datetime.now(timezone.utc).isoformat()}, ensure_ascii=False)}\n\n"

        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message.get("type") == "message":
                    raw = message.get("data")
                    if isinstance(raw, (bytes, bytearray)):
                        raw = raw.decode("utf-8", errors="ignore")
                    try:
                        decoded = json.loads(raw) if isinstance(raw, str) else {}
                    except Exception:
                        decoded = {}

                    event_type = decoded.get("type")
                    payload = decoded.get("payload") or {}
                    if event_type:
                        yield f"event: {event_type}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

                now = time.monotonic()
                if now - last_ping >= 15:
                    last_ping = now
                    yield f"event: ping\ndata: {json.dumps({'ts': datetime.now(timezone.utc).isoformat()})}\n\n"
        finally:
            await pubsub.unsubscribe(OPS_EVENTS_CHANNEL)
            await pubsub.close()

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/analytics/intelligence", summary="AI Intelligence analytics summary")
async def get_intelligence_stats(
    days: int = 7,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    from sqlalchemy import select, func, and_, extract
    from app.models import LLMLog
    from datetime import datetime, timedelta, timezone
    from decimal import Decimal
    
    since = datetime.now(timezone.utc) - timedelta(days=days)
    
    # 1. Basic metrics
    stmt = select(
        func.count(LLMLog.id).label("total_requests"),
        func.sum(LLMLog.cost_usd).label("total_cost"),
        func.sum(LLMLog.total_tokens).label("total_tokens"),
        func.avg(LLMLog.latency_ms).label("avg_latency")
    ).where(LLMLog.created_at >= since)
    
    res = await db.execute(stmt)
    metrics = res.one()
    
    # 2. Provider distribution
    provider_stmt = select(
        LLMLog.provider,
        func.count(LLMLog.id).label("count"),
        func.sum(LLMLog.cost_usd).label("cost")
    ).where(LLMLog.created_at >= since).group_by(LLMLog.provider)
    
    providers_res = await db.execute(provider_stmt)
    providers = []
    for p in providers_res.all():
        cost_val = p.cost
        if isinstance(cost_val, Decimal):
            cost_val = float(cost_val)
        providers.append({
            "provider": p.provider, 
            "count": p.count, 
            "cost": cost_val or 0.0
        })
    
    # 3. Latency heatmap (by hour of day)
    latency_stmt = select(
        extract('hour', LLMLog.created_at).label("hour"),
        func.avg(LLMLog.latency_ms).label("avg_latency")
    ).where(LLMLog.created_at >= since).group_by("hour").order_by("hour")
    
    latency_res = await db.execute(latency_stmt)
    latency_data = []
    for l in latency_res.all():
        avg_lat = l.avg_latency
        if isinstance(avg_lat, Decimal):
            avg_lat = float(avg_lat)
        latency_data.append({
            "hour": int(l.hour), 
            "avg_latency": avg_lat or 0.0
        })
    
    # Prepare metrics with safe float conversion
    total_cost = metrics.total_cost
    if isinstance(total_cost, Decimal):
        total_cost = float(total_cost)
        
    avg_latency = metrics.avg_latency
    if isinstance(avg_latency, Decimal):
        avg_latency = float(avg_latency)
        
    return {
        "metrics": {
            "total_requests": metrics.total_requests or 0,
            "total_cost": total_cost or 0.0,
            "total_tokens": int(metrics.total_tokens or 0),
            "avg_latency": avg_latency or 0.0
        },
        "providers": providers,
        "latency_heatmap": latency_data
    }
@router.get("/health", summary="Detailed system health monitoring")
async def get_system_health(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    _ = Depends(verify_internal_token)
):
    import time
    from sqlalchemy import text
    
    start_time = time.time()
    
    # 1. DB Check
    db_healthy = False
    try:
        await db.execute(text("SELECT 1"))
        db_healthy = True
    except: pass
    
    # 2. Redis Check
    redis_healthy = False
    redis_info = {}
    try:
        await redis.ping()
        redis_healthy = True
        redis_info = await redis.info("memory")
    except: pass
    
    # 3. RabbitMQ Check (via management API if possible, or just skip if no URL)
    # Reusing logic from get_queue_stats but simpler
    
    latency_ms = int((time.time() - start_time) * 1000)
    
    return {
        "api": {
            "status": "Healthy",
            "latency": f"{latency_ms}ms",
            "uptime": "N/A" # Would need app start time tracking
        },
        "database": {
            "status": "Connected" if db_healthy else "ERROR",
            "engine": "PostgreSQL",
        },
        "redis": {
            "status": "Healthy" if redis_healthy else "ERROR",
            "memory_usage": f"{redis_info.get('used_memory_human', 'N/A')}",
        },
        "rabbitmq": {
            "status": "Healthy", # Placeholder, would need deeper check
        }
    }

from typing import AsyncGenerator
from fastapi.responses import StreamingResponse

@router.get("/sources/{source_id:int}/logs/stream", summary="Стрим логов паука в реальном времени")
async def get_source_log_stream(
    source_id: int,
    redis: Redis = Depends(get_redis),
):
    """
    SSE endpoint returning logs for a specific source from Redis Pub/Sub.
    """
    async def log_generator() -> AsyncGenerator[str, None]:
        channel_name = f"logs:source:{source_id}"
        buffer_key = f"{channel_name}:buffer"
        
        # Send buffered logs first
        buffered_logs = await redis.lrange(buffer_key, 0, -1)
        for log in buffered_logs:
            if isinstance(log, bytes):
                log = log.decode('utf-8')
            yield f"data: {log}\n\n"

        pubsub = redis.pubsub()
        await pubsub.subscribe(channel_name)
        
        try:
            if not buffered_logs:
                yield "data: [CONNECTED] Real-time log stream started...\n\n"
            
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=10.0)
                if message and message['type'] == 'message':
                    data = message['data']
                    if isinstance(data, bytes):
                        data = data.decode('utf-8')
                    yield f"data: {data}\n\n"
                else:
                    yield "data: :ping\n\n"
        finally:
            await pubsub.unsubscribe(channel_name)
            await pubsub.close()

    return StreamingResponse(log_generator(), media_type="text/event-stream")


from app.repositories.frontend_routing import FrontendRoutingRepository
from app.schemas.frontend import (
    FrontendAllowedHostCreate,
    FrontendAllowedHostDTO,
    FrontendAllowedHostUpdate,
    FrontendAppCreate,
    FrontendAppDTO,
    FrontendAppUpdate,
    FrontendProfileCreate,
    FrontendProfileDTO,
    FrontendProfileUpdate,
    FrontendReleaseCreate,
    FrontendReleaseDTO,
    FrontendReleaseUpdate,
    FrontendRuleCreate,
    FrontendRuleDTO,
    FrontendRuleUpdate,
    FrontendRuntimeStateDTO,
    FrontendRuntimeStateUpdate,
    PublishRequest,
    RollbackRequest,
    ValidateReleaseResponse,
    FrontendAuditLogDTO,
)
from app.services.frontend_routing import FrontendRoutingService


async def require_frontend_reader(
    principal: str = Depends(verify_internal_token),
    db: AsyncSession = Depends(get_db),
) -> Optional[int]:
    if principal.startswith("tg_admin:"):
        user_id = int(principal.split(":", 1)[1])
        repo = TelegramRepository(db)
        subscriber = await repo.get_subscriber(user_id)
        if not subscriber or subscriber.role not in ["admin", "superadmin"]:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return user_id
    # system token path
    return None


async def require_frontend_manager(
    principal: str = Depends(verify_internal_token),
    db: AsyncSession = Depends(get_db),
) -> Optional[int]:
    if principal.startswith("tg_admin:"):
        user_id = int(principal.split(":", 1)[1])
        repo = TelegramRepository(db)
        subscriber = await repo.get_subscriber(user_id)
        if not subscriber or subscriber.role not in ["admin", "superadmin"]:
            raise HTTPException(status_code=403, detail="Insufficient role")
        if subscriber.role != "superadmin" and "frontend_release_manager" not in (subscriber.permissions or []):
            raise HTTPException(status_code=403, detail="Missing frontend_release_manager permission")
        return user_id
    # system token path
    return None


@router.get("/frontend/apps", response_model=List[FrontendAppDTO])
async def list_frontend_apps(
    db: AsyncSession = Depends(get_db),
    _actor_id: Optional[int] = Depends(require_frontend_reader),
):
    repo = FrontendRoutingRepository(db)
    return await repo.list_apps()


@router.post("/frontend/apps", response_model=FrontendAppDTO)
async def create_frontend_app(
    data: FrontendAppCreate,
    db: AsyncSession = Depends(get_db),
    actor_id: Optional[int] = Depends(require_frontend_manager),
):
    repo = FrontendRoutingRepository(db)
    return await repo.create_app(data.model_dump(), actor_id=actor_id)


@router.patch("/frontend/apps/{app_id}", response_model=FrontendAppDTO)
async def update_frontend_app(
    app_id: int,
    data: FrontendAppUpdate,
    db: AsyncSession = Depends(get_db),
    actor_id: Optional[int] = Depends(require_frontend_manager),
):
    repo = FrontendRoutingRepository(db)
    payload = data.model_dump(exclude_unset=True)
    row = await repo.update_app(app_id, payload, actor_id=actor_id)
    if not row:
        raise HTTPException(status_code=404, detail="App not found")
    return row


@router.delete("/frontend/apps/{app_id}")
async def delete_frontend_app(
    app_id: int,
    db: AsyncSession = Depends(get_db),
    actor_id: Optional[int] = Depends(require_frontend_manager),
):
    repo = FrontendRoutingRepository(db)
    ok = await repo.delete_app(app_id, actor_id=actor_id)
    if not ok:
        raise HTTPException(status_code=404, detail="App not found")
    return {"status": "ok"}


@router.get("/frontend/releases", response_model=List[FrontendReleaseDTO])
async def list_frontend_releases(
    app_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    _actor_id: Optional[int] = Depends(require_frontend_reader),
):
    repo = FrontendRoutingRepository(db)
    return await repo.list_releases(app_id=app_id)


@router.post("/frontend/releases", response_model=FrontendReleaseDTO)
async def create_frontend_release(
    data: FrontendReleaseCreate,
    db: AsyncSession = Depends(get_db),
    actor_id: Optional[int] = Depends(require_frontend_manager),
):
    repo = FrontendRoutingRepository(db)
    return await repo.create_release(data.model_dump(), actor_id=actor_id)


@router.patch("/frontend/releases/{release_id}", response_model=FrontendReleaseDTO)
async def update_frontend_release(
    release_id: int,
    data: FrontendReleaseUpdate,
    db: AsyncSession = Depends(get_db),
    actor_id: Optional[int] = Depends(require_frontend_manager),
):
    repo = FrontendRoutingRepository(db)
    payload = data.model_dump(exclude_unset=True)
    row = await repo.update_release(release_id, payload, actor_id=actor_id)
    if not row:
        raise HTTPException(status_code=404, detail="Release not found")
    return row


@router.delete("/frontend/releases/{release_id}")
async def delete_frontend_release(
    release_id: int,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    actor_id: Optional[int] = Depends(require_frontend_manager),
):
    repo = FrontendRoutingRepository(db)
    ok = await repo.delete_release(release_id, actor_id=actor_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Release not found")
    service = FrontendRoutingService(db=db, redis=redis)
    await service.invalidate_runtime_cache()
    return {"status": "ok"}


@router.post("/frontend/releases/{release_id}/validate", response_model=ValidateReleaseResponse)
async def validate_frontend_release(
    release_id: int,
    db: AsyncSession = Depends(get_db),
    actor_id: Optional[int] = Depends(require_frontend_manager),
):
    service = FrontendRoutingService(db=db)
    try:
        result = await service.validate_release(release_id)
    except ValueError as exc:
        # Service raises ValueError("release not found") for missing rows.
        raise HTTPException(status_code=404, detail=str(exc))

    resp = ValidateReleaseResponse(**result)
    # Audit payload must be JSON-serializable (e.g. datetime -> isoformat), so use Pydantic json mode.
    if actor_id is not None:
        repo = FrontendRoutingRepository(db)
        await repo._audit(
            actor_id=actor_id,
            action="validate",
            entity_type="frontend_release",
            entity_id=str(release_id),
            after=resp.model_dump(mode="json"),
        )
        await db.commit()
    return resp


@router.get("/frontend/profiles", response_model=List[FrontendProfileDTO])
async def list_frontend_profiles(
    db: AsyncSession = Depends(get_db),
    _actor_id: Optional[int] = Depends(require_frontend_reader),
):
    repo = FrontendRoutingRepository(db)
    return await repo.list_profiles()


@router.post("/frontend/profiles", response_model=FrontendProfileDTO)
async def create_frontend_profile(
    data: FrontendProfileCreate,
    db: AsyncSession = Depends(get_db),
    actor_id: Optional[int] = Depends(require_frontend_manager),
):
    repo = FrontendRoutingRepository(db)
    return await repo.create_profile(data.model_dump(), actor_id=actor_id)


@router.patch("/frontend/profiles/{profile_id}", response_model=FrontendProfileDTO)
async def update_frontend_profile(
    profile_id: int,
    data: FrontendProfileUpdate,
    db: AsyncSession = Depends(get_db),
    actor_id: Optional[int] = Depends(require_frontend_manager),
):
    repo = FrontendRoutingRepository(db)
    payload = data.model_dump(exclude_unset=True)
    row = await repo.update_profile(profile_id, payload, actor_id=actor_id)
    if not row:
        raise HTTPException(status_code=404, detail="Profile not found")
    return row


@router.get("/frontend/rules", response_model=List[FrontendRuleDTO])
async def list_frontend_rules(
    profile_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    _actor_id: Optional[int] = Depends(require_frontend_reader),
):
    repo = FrontendRoutingRepository(db)
    return await repo.list_rules(profile_id=profile_id)


@router.post("/frontend/rules", response_model=FrontendRuleDTO)
async def create_frontend_rule(
    data: FrontendRuleCreate,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    actor_id: Optional[int] = Depends(require_frontend_manager),
):
    repo = FrontendRoutingRepository(db)
    row = await repo.create_rule(data.model_dump(), actor_id=actor_id)
    service = FrontendRoutingService(db=db, redis=redis)
    await service.invalidate_runtime_cache()
    return row


@router.patch("/frontend/rules/{rule_id}", response_model=FrontendRuleDTO)
async def update_frontend_rule(
    rule_id: int,
    data: FrontendRuleUpdate,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    actor_id: Optional[int] = Depends(require_frontend_manager),
):
    repo = FrontendRoutingRepository(db)
    payload = data.model_dump(exclude_unset=True)
    row = await repo.update_rule(rule_id, payload, actor_id=actor_id)
    if not row:
        raise HTTPException(status_code=404, detail="Rule not found")
    service = FrontendRoutingService(db=db, redis=redis)
    await service.invalidate_runtime_cache()
    return row


@router.delete("/frontend/rules/{rule_id}")
async def delete_frontend_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    actor_id: Optional[int] = Depends(require_frontend_manager),
):
    repo = FrontendRoutingRepository(db)
    ok = await repo.delete_rule(rule_id, actor_id=actor_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Rule not found")
    service = FrontendRoutingService(db=db, redis=redis)
    await service.invalidate_runtime_cache()
    return {"status": "ok"}


@router.get("/frontend/runtime-state", response_model=FrontendRuntimeStateDTO)
async def get_frontend_runtime_state(
    db: AsyncSession = Depends(get_db),
    _actor_id: Optional[int] = Depends(require_frontend_reader),
):
    repo = FrontendRoutingRepository(db)
    state = await repo.get_runtime_state()
    if not state:
        raise HTTPException(status_code=404, detail="Runtime state not found")
    return state


@router.patch("/frontend/runtime-state", response_model=FrontendRuntimeStateDTO)
async def update_frontend_runtime_state(
    data: FrontendRuntimeStateUpdate,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    actor_id: Optional[int] = Depends(require_frontend_manager),
):
    repo = FrontendRoutingRepository(db)
    payload = data.model_dump(exclude_unset=True)
    state = await repo.set_runtime_state(payload, actor_id=actor_id)
    service = FrontendRoutingService(db=db, redis=redis)
    await service.invalidate_runtime_cache()
    return state


@router.get("/frontend/allowed-hosts", response_model=List[FrontendAllowedHostDTO])
async def list_frontend_allowed_hosts(
    db: AsyncSession = Depends(get_db),
    _actor_id: Optional[int] = Depends(require_frontend_reader),
):
    repo = FrontendRoutingRepository(db)
    return await repo.list_allowed_hosts()


@router.post("/frontend/allowed-hosts", response_model=FrontendAllowedHostDTO)
async def create_frontend_allowed_host(
    data: FrontendAllowedHostCreate,
    db: AsyncSession = Depends(get_db),
    actor_id: Optional[int] = Depends(require_frontend_manager),
):
    repo = FrontendRoutingRepository(db)
    return await repo.create_allowed_host(data.model_dump(), actor_id=actor_id)


@router.patch("/frontend/allowed-hosts/{host_id}", response_model=FrontendAllowedHostDTO)
async def update_frontend_allowed_host(
    host_id: int,
    data: FrontendAllowedHostUpdate,
    db: AsyncSession = Depends(get_db),
    actor_id: Optional[int] = Depends(require_frontend_manager),
):
    repo = FrontendRoutingRepository(db)
    payload = data.model_dump(exclude_unset=True)
    row = await repo.update_allowed_host(host_id, payload, actor_id=actor_id)
    if not row:
        raise HTTPException(status_code=404, detail="Allowed host not found")
    return row


@router.delete("/frontend/allowed-hosts/{host_id}")
async def delete_frontend_allowed_host(
    host_id: int,
    db: AsyncSession = Depends(get_db),
    actor_id: Optional[int] = Depends(require_frontend_manager),
):
    repo = FrontendRoutingRepository(db)
    ok = await repo.delete_allowed_host(host_id, actor_id=actor_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Allowed host not found")
    return {"status": "ok"}


@router.post("/frontend/publish", response_model=FrontendRuntimeStateDTO)
async def publish_frontend_config(
    data: PublishRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    actor_id: Optional[int] = Depends(require_frontend_manager),
):
    repo = FrontendRoutingRepository(db)
    state = await repo.publish(
        active_profile_id=data.active_profile_id,
        fallback_release_id=data.fallback_release_id,
        actor_id=actor_id,
        sticky_enabled=data.sticky_enabled,
        sticky_ttl_seconds=data.sticky_ttl_seconds,
        cache_ttl_seconds=data.cache_ttl_seconds,
    )
    service = FrontendRoutingService(db=db, redis=redis)
    await service.invalidate_runtime_cache()
    return state


@router.post("/frontend/rollback", response_model=FrontendRuntimeStateDTO)
async def rollback_frontend_config(
    data: RollbackRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    actor_id: Optional[int] = Depends(require_frontend_manager),
):
    repo = FrontendRoutingRepository(db)
    state = await repo.rollback(actor_id=actor_id, app_id=data.app_id)
    if not state:
        raise HTTPException(status_code=400, detail="Rollback target not found")
    service = FrontendRoutingService(db=db, redis=redis)
    await service.invalidate_runtime_cache()
    return state


@router.get("/frontend/audit-log", response_model=List[FrontendAuditLogDTO])
async def list_frontend_audit_log(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _actor_id: Optional[int] = Depends(require_frontend_reader),
):
    repo = FrontendRoutingRepository(db)
    return await repo.list_audit_log(limit=limit, offset=offset)
