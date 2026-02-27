from __future__ import annotations

import logging
import time
from typing import Iterable

from app.db import get_redis, get_session_context
from routes.internal import (
    _compute_ops_items_trend_payload,
    _compute_ops_overview_payload,
    _compute_ops_scheduler_stats_payload,
    _compute_ops_tasks_trend_payload,
    _get_or_create_ops_runtime_state,
    _publish_ops_event,
    _snapshot_key,
    _snapshot_meta_get,
    _snapshot_write,
    ops_aggregator_run_duration_ms,
    ops_aggregator_runs_total,
    ops_snapshot_refresh_errors_total,
)

logger = logging.getLogger(__name__)
OPS_AGGREGATOR_LOCK_KEY = "ops:aggregator:lock"
OPS_AGGREGATOR_LOCK_TTL_SECONDS = 25

TREND_COMBOS: tuple[tuple[str, int], ...] = (
    ("week", 12),
    ("day", 30),
    ("hour", 72),
    ("minute", 180),
)


async def _with_leader_lock(redis, worker_id: str) -> bool:
    try:
        acquired = await redis.set(
            OPS_AGGREGATOR_LOCK_KEY,
            worker_id,
            ex=OPS_AGGREGATOR_LOCK_TTL_SECONDS,
            nx=True,
        )
        return bool(acquired)
    except Exception:
        return False


async def _refresh_block(
    *,
    redis,
    block: str,
    cache_key: str,
    payload: dict,
    ttl_ms: int,
) -> None:
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


async def run_ops_aggregator_tick(*, worker_id: str = "scheduler:default") -> None:
    started = time.perf_counter()
    ops_aggregator_runs_total.inc()
    redis = await get_redis()

    if not await _with_leader_lock(redis, worker_id=worker_id):
        return

    try:
        async with get_session_context() as db:
            state = await _get_or_create_ops_runtime_state(db)
            if not bool(state.ops_aggregator_enabled):
                return

            ttl_ms = int(state.ops_snapshot_ttl_ms or 10000)

            overview_payload = await _compute_ops_overview_payload(db=db, redis=redis)
            await _refresh_block(
                redis=redis,
                block="overview",
                cache_key=_snapshot_key("overview"),
                payload=overview_payload,
                ttl_ms=ttl_ms,
            )

            scheduler_payload = await _compute_ops_scheduler_stats_payload(db=db)
            await _refresh_block(
                redis=redis,
                block="scheduler_stats",
                cache_key=_snapshot_key("scheduler_stats"),
                payload=scheduler_payload,
                ttl_ms=ttl_ms,
            )

            for granularity, buckets in TREND_COMBOS:
                items_payload = await _compute_ops_items_trend_payload(
                    granularity=granularity,
                    buckets=buckets,
                    days=None,
                    db=db,
                )
                await _refresh_block(
                    redis=redis,
                    block="items_trend",
                    cache_key=_snapshot_key("items_trend", granularity=granularity, buckets=buckets),
                    payload=items_payload,
                    ttl_ms=ttl_ms,
                )

                tasks_payload = await _compute_ops_tasks_trend_payload(
                    granularity=granularity,
                    buckets=buckets,
                    redis=redis,
                )
                await _refresh_block(
                    redis=redis,
                    block="tasks_trend",
                    cache_key=_snapshot_key("tasks_trend", granularity=granularity, buckets=buckets),
                    payload=tasks_payload,
                    ttl_ms=ttl_ms,
                )
    except Exception:
        ops_snapshot_refresh_errors_total.inc()
        logger.exception("Ops aggregator tick failed")
    finally:
        ops_aggregator_run_duration_ms.observe((time.perf_counter() - started) * 1000.0)
