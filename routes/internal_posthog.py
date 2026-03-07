from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from redis.asyncio import Redis

from app.config import get_settings
from app.db import get_redis
from app.schemas.analytics import PostHogStatsResponse
from app.services.posthog_analytics import get_posthog_kpis
from routes.internal import verify_internal_token

router = APIRouter(prefix="/api/v1/internal/analytics/posthog", tags=["internal"])


def _is_ip_allowed(client_ip: str, allowlist_raw: Optional[str]) -> bool:
    if not allowlist_raw:
        return True
    allowlist = {item.strip() for item in allowlist_raw.split(",") if item.strip()}
    if not allowlist:
        return True
    return client_ip in allowlist


async def _enforce_rate_limit(request: Request, redis: Redis) -> None:
    settings = get_settings()
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"rate_limit:internal_posthog_stats:{client_ip}"
    current = await redis.incr(rate_key)
    if current == 1:
        await redis.expire(rate_key, 60)
    if current > max(1, int(settings.posthog_stats_rate_limit_per_minute)):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")


@router.get("/stats", response_model=PostHogStatsResponse)
async def get_internal_posthog_stats(
    request: Request,
    redis: Redis = Depends(get_redis),
    _auth: str = Depends(verify_internal_token),
):
    settings = get_settings()
    client_ip = request.client.host if request.client else "unknown"

    if not _is_ip_allowed(client_ip, settings.posthog_stats_allowlist_ips):
        raise HTTPException(status_code=403, detail="IP is not allowed for PostHog analytics")

    await _enforce_rate_limit(request, redis)

    payload = await get_posthog_kpis(settings=settings, redis=redis)
    return PostHogStatsResponse(**payload)
