from __future__ import annotations

import json
import asyncio
from datetime import datetime, timezone
from typing import Any

import httpx
from redis.asyncio import Redis

from app.config import Settings

POSTHOG_API_BASE = "https://app.posthog.com/api"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _extract_last_numeric(data: dict[str, Any]) -> int:
    results = data.get("results") or []
    if not results:
        return 0
    series = results[0].get("data") if isinstance(results[0], dict) else None
    if not series:
        return 0
    return _safe_int(series[-1])


def _extract_funnel_steps(data: dict[str, Any]) -> tuple[int, int]:
    results = data.get("results") or []
    if not results:
        return 0, 0
    steps = results[0] if isinstance(results[0], list) else results
    if not isinstance(steps, list):
        return 0, 0
    started = 0
    completed_or_clicked = 0
    if len(steps) > 0:
        started = _safe_int(steps[0].get("count") if isinstance(steps[0], dict) else steps[0])
    if len(steps) > 1:
        completed_or_clicked = _safe_int(steps[1].get("count") if isinstance(steps[1], dict) else steps[1])
    return started, completed_or_clicked


async def _query_posthog(
    *,
    query: dict[str, Any],
    settings: Settings,
    timeout_seconds: float,
    max_retries: int,
) -> dict[str, Any]:
    if not settings.posthog_api_key or not settings.posthog_project_id:
        raise RuntimeError("PostHog integration not configured")

    url = f"{POSTHOG_API_BASE}/projects/{settings.posthog_project_id}/query/"
    headers = {
        "Authorization": f"Bearer {settings.posthog_api_key}",
        "Content-Type": "application/json",
    }

    attempts = max(1, int(max_retries) + 1)
    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        for attempt in range(attempts):
            try:
                response = await client.post(url, headers=headers, json={"query": query})
                response.raise_for_status()
                return response.json()
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                last_error = exc
                if attempt == attempts - 1:
                    break
    raise RuntimeError(f"PostHog query failed: {last_error}")


def _cache_keys(prefix: str) -> tuple[str, str]:
    return f"{prefix}:fresh", f"{prefix}:stale"


async def get_posthog_kpis(
    *,
    settings: Settings,
    redis: Redis,
    cache_prefix: str = "analytics:posthog:kpis:v1",
) -> dict[str, Any]:
    fresh_key, stale_key = _cache_keys(cache_prefix)

    cached_fresh = await redis.get(fresh_key)
    if cached_fresh:
        payload = json.loads(cached_fresh)
        payload["source"] = "cache"
        payload["stale"] = False
        payload["cache_age_seconds"] = 0
        return payload

    try:
        dau_query = {
            "kind": "TrendsQuery",
            "series": [{"event": "page_viewed", "math": "dau"}],
            "dateRange": {"date_from": "-1d"},
        }
        quiz_query = {
            "kind": "FunnelsQuery",
            "series": [{"event": "quiz_started"}, {"event": "quiz_completed"}],
            "dateRange": {"date_from": "-7d"},
        }
        gift_query = {
            "kind": "FunnelsQuery",
            "series": [{"event": "results_shown"}, {"event": "gift_clicked"}],
            "dateRange": {"date_from": "-7d"},
        }

        dau_data, quiz_data, gift_data = await asyncio.gather(
            _query_posthog(
                query=dau_query,
                settings=settings,
                timeout_seconds=settings.posthog_timeout_seconds,
                max_retries=settings.posthog_max_retries,
            ),
            _query_posthog(
                query=quiz_query,
                settings=settings,
                timeout_seconds=settings.posthog_timeout_seconds,
                max_retries=settings.posthog_max_retries,
            ),
            _query_posthog(
                query=gift_query,
                settings=settings,
                timeout_seconds=settings.posthog_timeout_seconds,
                max_retries=settings.posthog_max_retries,
            ),
        )

        dau = _extract_last_numeric(dau_data)
        started, completed = _extract_funnel_steps(quiz_data)
        shown, clicked = _extract_funnel_steps(gift_data)

        quiz_completion_rate = round((completed / started) * 100, 2) if started else 0.0
        gift_ctr = round((clicked / shown) * 100, 2) if shown else 0.0

        payload = {
            "dau": dau,
            "quiz_completion_rate": quiz_completion_rate,
            "gift_ctr": gift_ctr,
            "total_sessions": started,
            "source": "live",
            "stale": False,
            "cache_age_seconds": 0,
            "last_updated": _iso_now(),
        }

        await redis.setex(fresh_key, settings.posthog_stats_cache_ttl_seconds, json.dumps(payload))
        await redis.setex(stale_key, settings.posthog_stats_stale_ttl_seconds, json.dumps(payload))
        return payload
    except Exception:
        cached_stale = await redis.get(stale_key)
        if cached_stale:
            payload = json.loads(cached_stale)
            payload["source"] = "stale_cache"
            payload["stale"] = True
            updated_at = payload.get("last_updated")
            if updated_at:
                try:
                    age = datetime.now(timezone.utc) - datetime.fromisoformat(updated_at)
                    payload["cache_age_seconds"] = max(0, int(age.total_seconds()))
                except Exception:
                    payload["cache_age_seconds"] = None
            else:
                payload["cache_age_seconds"] = None
            return payload

        return {
            "dau": 0,
            "quiz_completion_rate": 0.0,
            "gift_ctr": 0.0,
            "total_sessions": 0,
            "source": "unavailable",
            "stale": True,
            "cache_age_seconds": None,
            "last_updated": _iso_now(),
        }
