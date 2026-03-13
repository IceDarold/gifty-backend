from __future__ import annotations

import argparse
import asyncio
import logging
import os
import time
from datetime import datetime, timezone, timedelta
from typing import Iterable, List, Optional, Tuple

from clickhouse_driver import Client
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, push_to_gateway
from sqlalchemy import and_, or_, select

from app.config import get_settings
from app.db import get_session_context
from app.models import LLMLog

logger = logging.getLogger("pg_ch_backfill")

METRICS_REGISTRY = CollectorRegistry()
backfill_rows_total = Counter(
    "pg_ch_backfill_rows_total",
    "Rows backfilled into ClickHouse",
    ["table"],
    registry=METRICS_REGISTRY,
)
backfill_duration_seconds = Histogram(
    "pg_ch_backfill_duration_seconds",
    "Backfill duration in seconds",
    buckets=(1, 5, 10, 30, 60, 120, 300, 600, 1200),
    registry=METRICS_REGISTRY,
)
backfill_window_seconds = Gauge(
    "pg_ch_backfill_window_seconds",
    "Backfill window duration in seconds",
    registry=METRICS_REGISTRY,
)
backfill_window_from_ts = Gauge(
    "pg_ch_backfill_window_from_timestamp",
    "Backfill window start timestamp (seconds since epoch)",
    registry=METRICS_REGISTRY,
)
backfill_window_to_ts = Gauge(
    "pg_ch_backfill_window_to_timestamp",
    "Backfill window end timestamp (seconds since epoch)",
    registry=METRICS_REGISTRY,
)


def _ch_client() -> Client:
    settings = get_settings()
    host = "clickhouse"
    port = 9000
    user = "analytics"
    password = "analytics"
    database = "default"
    dsn = getattr(settings, "clickhouse_dsn", "") or ""
    if "clickhouse://" in dsn:
        no_scheme = dsn.split("://", 1)[1]
        creds_host = no_scheme.split("/", 1)[0]
        if "@" in creds_host:
            creds, hostport = creds_host.split("@", 1)
            host = hostport.split(":", 1)[0] or host
            if ":" in hostport:
                port = int(hostport.split(":", 1)[1])
            if ":" in creds:
                user, password = creds.split(":", 1)
        else:
            host = creds_host.split(":", 1)[0] or host
    return Client(host=host, port=port, user=user, password=password, database=database)


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    v = value.strip()
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(v).astimezone(timezone.utc)
    except Exception:
        return None


def _to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _sync_state_latest(client: Client, sync_name: str) -> Optional[dict]:
    q = """
        SELECT sync_name, last_bootstrap_at, last_bootstrap_version, last_event_applied_at, last_event_id, lag_seconds, last_backfill_at
        FROM sync_state FINAL
        WHERE sync_name = %(name)s
        ORDER BY last_bootstrap_version DESC
        LIMIT 1
    """
    rows = client.execute(q, {"name": sync_name})
    if not rows:
        return None
    row = rows[0]
    return {
        "sync_name": row[0],
        "last_bootstrap_at": row[1],
        "last_bootstrap_version": row[2],
        "last_event_applied_at": row[3],
        "last_event_id": row[4],
        "lag_seconds": row[5],
        "last_backfill_at": row[6],
    }


def _update_backfill_state(client: Client, window_from: datetime, window_to: datetime) -> None:
    now = datetime.now(timezone.utc)
    state = _sync_state_latest(client, "analytics-events") or {}
    client.execute(
        "INSERT INTO sync_state (sync_name, last_bootstrap_at, last_bootstrap_version, last_event_applied_at, last_event_id, lag_seconds, last_backfill_at) VALUES",
        [
            (
                "pg-ch-backfill",
                state.get("last_bootstrap_at") or now,
                int(now.timestamp()),
                state.get("last_event_applied_at") or window_to,
                state.get("last_event_id") or "",
                float(max(0.0, (now - window_to).total_seconds())),
                now,
            )
        ],
    )


def _llm_log_rows(logs: Iterable[LLMLog]) -> Tuple[List[tuple], List[tuple]]:
    import json

    now = datetime.now(timezone.utc)
    events: List[tuple] = []
    metrics: List[tuple] = []
    calls: List[tuple] = []
    for log in logs:
        created_at = getattr(log, "created_at", now) or now
        event_id = f"llm.log:{log.id}"
        payload = {
            "id": str(log.id),
            "provider": log.provider,
            "model": log.model,
            "call_type": log.call_type,
            "status": log.status,
            "error_type": log.error_type,
            "error_message": log.error_message,
            "prompt_tokens": log.prompt_tokens,
            "completion_tokens": log.completion_tokens,
            "total_tokens": log.total_tokens,
            "latency_ms": log.latency_ms,
            "provider_latency_ms": log.provider_latency_ms,
            "queue_latency_ms": log.queue_latency_ms,
            "postprocess_latency_ms": log.postprocess_latency_ms,
            "cost_usd": float(log.cost_usd) if log.cost_usd is not None else None,
            "provider_request_id": log.provider_request_id,
            "prompt_hash": log.prompt_hash,
            "session_id": log.session_id,
            "experiment_id": log.experiment_id,
            "variant_id": log.variant_id,
            "finish_reason": log.finish_reason,
            "params": log.params,
            "system_prompt": log.system_prompt,
            "output_content": log.output_content,
            "created_at": created_at,
            "usage_captured": True,
            "provider_request_captured": True,
        }
        dims = json.dumps(
            {
                "provider": log.provider,
                "model": log.model,
                "call_type": log.call_type,
                "status": log.status,
            },
            default=str,
        )
        events.append(
            (
                event_id,
                created_at,
                "llm.log",
                "",
                "",
                "",
                dims,
                json.dumps(payload, default=str),
                0.0,
                int(created_at.timestamp()),
            )
        )
        metric_event_id = f"llm.call_completed:{log.id}"
        metrics.extend(
            [
                (
                    metric_event_id,
                    created_at,
                    "llm.call_completed",
                    "llm.call_completed",
                    "",
                    "",
                    dims,
                    "",
                    1.0,
                    int(created_at.timestamp()),
                ),
                (
                    metric_event_id,
                    created_at,
                    "llm.call_completed",
                    "llm.call_completed.total_tokens",
                    "",
                    "",
                    dims,
                    "",
                    float(log.total_tokens or 0),
                    int(created_at.timestamp()),
                ),
                (
                    metric_event_id,
                    created_at,
                    "llm.call_completed",
                    "llm.call_completed.latency_ms",
                    "",
                    "",
                    dims,
                    "",
                    float(log.latency_ms or 0),
                    int(created_at.timestamp()),
                ),
                (
                    metric_event_id,
                    created_at,
                    "llm.call_completed",
                    "llm.call_completed.cost_usd",
                    "",
                    "",
                    dims,
                    "",
                    float(log.cost_usd or 0),
                int(created_at.timestamp()),
            ),
        ]
        )
        calls.append(
            (
                event_id,
                created_at,
                log.provider or "",
                log.model or "",
                log.call_type or "",
                log.status or "",
                float(log.latency_ms or 0),
                int(log.total_tokens or 0),
                int(log.prompt_tokens or 0),
                int(log.completion_tokens or 0),
                float(log.cost_usd or 0),
                log.session_id or "",
                log.prompt_hash or "",
                json.dumps(payload, default=str),
                int(created_at.timestamp()),
            )
        )
    return events, metrics, calls


async def _backfill_llm_logs(session, client: Client, window_from: datetime, window_to: datetime, batch_size: int) -> int:
    total = 0
    last_created_at: Optional[datetime] = None
    last_id = None
    while True:
        conditions = [LLMLog.created_at >= window_from, LLMLog.created_at < window_to]
        if last_created_at is not None and last_id is not None:
            conditions.append(
                or_(
                    LLMLog.created_at > last_created_at,
                    and_(LLMLog.created_at == last_created_at, LLMLog.id > last_id),
                )
            )
        result = await session.execute(
            select(LLMLog)
            .where(and_(*conditions))
            .order_by(LLMLog.created_at.asc(), LLMLog.id.asc())
            .limit(batch_size)
        )
        logs = list(result.scalars().all())
        if not logs:
            break
        events, metrics, calls = _llm_log_rows(logs)
        if events:
            client.execute(
                "INSERT INTO analytics_events (event_id, occurred_at, event_type, metric, scope, scope_key, dims_json, payload_json, value, version) VALUES",
                events,
            )
        if metrics:
            client.execute(
                "INSERT INTO analytics_events (event_id, occurred_at, event_type, metric, scope, scope_key, dims_json, payload_json, value, version) VALUES",
                metrics,
            )
        if calls:
            client.execute(
                "INSERT INTO llm_calls (event_id, created_at, provider, model, call_type, status, latency_ms, total_tokens, prompt_tokens, completion_tokens, cost_usd, session_id, prompt_hash, payload_json, version) VALUES",
                calls,
            )
        total += len(logs)
        last_created_at = logs[-1].created_at
        last_id = logs[-1].id
        if len(logs) < batch_size:
            break
    return total


async def run_backfill(window_from: datetime, window_to: datetime, tables: List[str], batch_size: int) -> None:
    start = time.time()
    backfill_window_seconds.set(max(0.0, (window_to - window_from).total_seconds()))
    backfill_window_from_ts.set(window_from.timestamp())
    backfill_window_to_ts.set(window_to.timestamp())
    client = _ch_client()
    async with get_session_context() as session:
        if "llm_logs" in tables:
            logger.info("Backfill llm_logs: %s -> %s", _to_iso(window_from), _to_iso(window_to))
            count = await _backfill_llm_logs(session, client, window_from, window_to, batch_size)
            logger.info("Backfill llm_logs rows=%s", count)
            backfill_rows_total.labels(table="llm_logs").inc(count)
        for name in tables:
            if name == "llm_logs":
                continue
            logger.warning("Backfill table '%s' not implemented (skip)", name)
    _update_backfill_state(client, window_from, window_to)
    duration = max(0.0, time.time() - start)
    backfill_duration_seconds.observe(duration)
    _push_metrics()


def _resolve_window(args_from: Optional[str], args_to: Optional[str]) -> Tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    default_days = int(os.getenv("BACKFILL_DEFAULT_DAYS", "7") or "7")
    dt_from = _parse_dt(args_from) or (now - timedelta(days=default_days))
    dt_to = _parse_dt(args_to) or now
    if dt_from >= dt_to:
        dt_from = dt_to - timedelta(days=default_days)
    return dt_from, dt_to


async def run_auto(tables: List[str], batch_size: int) -> None:
    client = _ch_client()
    gap_seconds = int(os.getenv("BACKFILL_GAP_SECONDS", "3600") or "3600")
    state = _sync_state_latest(client, "analytics-events")
    if not state or not state.get("last_event_applied_at"):
        logger.warning("sync_state missing; running backfill with default window")
        window_from, window_to = _resolve_window(None, None)
        await run_backfill(window_from, window_to, tables, batch_size)
        return
    last_event_at: datetime = state["last_event_applied_at"]
    now = datetime.now(timezone.utc)
    gap = (now - last_event_at).total_seconds()
    if gap < gap_seconds:
        logger.info("Gap %.0fs < threshold %ss; backfill skipped", gap, gap_seconds)
        return
    window_from = last_event_at
    window_to = now
    logger.info("Gap %.0fs detected; running backfill", gap)
    await run_backfill(window_from, window_to, tables, batch_size)


def _push_metrics() -> None:
    gateway = os.getenv("PROMETHEUS_PUSHGATEWAY", "").strip()
    if not gateway:
        return
    job = os.getenv("BACKFILL_METRICS_JOB", "pg_ch_backfill")
    try:
        push_to_gateway(gateway, job=job, registry=METRICS_REGISTRY)
    except Exception:
        logger.exception("Failed to push backfill metrics to Prometheus gateway")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill ClickHouse from Postgres.")
    parser.add_argument("--from", dest="from_ts", default=None, help="UTC ISO timestamp start")
    parser.add_argument("--to", dest="to_ts", default=None, help="UTC ISO timestamp end")
    parser.add_argument("--tables", default="llm_logs", help="Comma-separated tables to backfill")
    parser.add_argument("--batch", type=int, default=int(os.getenv("BACKFILL_BATCH_SIZE", "1000") or "1000"))
    parser.add_argument("--auto", action="store_true", help="Auto window from sync_state gap")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tables = [t.strip() for t in (args.tables or "").split(",") if t.strip()]
    if not tables:
        tables = ["llm_logs"]
    if args.auto:
        asyncio.run(run_auto(tables, args.batch))
        return
    window_from, window_to = _resolve_window(args.from_ts, args.to_ts)
    asyncio.run(run_backfill(window_from, window_to, tables, args.batch))


if __name__ == "__main__":
    main()
