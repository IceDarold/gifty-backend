from __future__ import annotations

import hashlib
import json
import logging
import time
from copy import deepcopy
from datetime import datetime, timezone
from fnmatch import fnmatch
from typing import Any, Optional
from urllib.parse import urlparse

import httpx
from prometheus_client import Counter, Histogram
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.frontend_routing import FrontendRoutingRepository
from app.schemas.frontend import FrontendConfigRequest, FrontendConfigResponse

logger = logging.getLogger(__name__)

frontend_config_requests_total = Counter(
    "frontend_config_requests_total",
    "Total frontend routing config requests",
)
frontend_config_cache_hits_total = Counter(
    "frontend_config_cache_hits_total",
    "Frontend routing cache hits",
)
frontend_config_fallback_total = Counter(
    "frontend_config_fallback_total",
    "Frontend routing fallback usage count",
)
frontend_config_resolution_latency_ms = Histogram(
    "frontend_config_resolution_latency_ms",
    "Frontend routing resolution latency in milliseconds",
    buckets=(1, 3, 5, 10, 20, 50, 100, 200, 500),
)


class FrontendRoutingService:
    STICKY_COOKIE_NAME = "gifty_frontend_release"

    def __init__(self, db: AsyncSession, redis: Optional[Redis] = None):
        self.db = db
        self.redis = redis
        self.repo = FrontendRoutingRepository(db)

    @staticmethod
    def _normalize_host(host: str) -> str:
        host = (host or "").strip().lower()
        if ":" in host:
            host = host.split(":", 1)[0]
        return host

    @staticmethod
    def _normalize_path(path: str) -> str:
        if not path:
            return "/"
        return path if path.startswith("/") else f"/{path}"

    @staticmethod
    def _query_hash(params: dict[str, str]) -> str:
        payload = json.dumps(params, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]

    @staticmethod
    def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(base)
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = FrontendRoutingService._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    async def _cache_get(self, key: str) -> Optional[dict[str, Any]]:
        if not self.redis:
            return None
        cached = await self.redis.get(key)
        if not cached:
            return None
        frontend_config_cache_hits_total.inc()
        try:
            return json.loads(cached)
        except Exception:
            return None

    async def _cache_set(self, key: str, value: dict[str, Any], ttl: int) -> None:
        if not self.redis:
            return
        await self.redis.setex(key, max(1, ttl), json.dumps(value))

    async def invalidate_runtime_cache(self) -> None:
        if not self.redis:
            return
        cursor = 0
        pattern = "frontend:cfg:*"
        while True:
            cursor, keys = await self.redis.scan(cursor=cursor, match=pattern, count=200)
            if keys:
                await self.redis.delete(*keys)
            if cursor == 0:
                break

    async def _get_release_by_id(self, release_id: int):
        return await self.repo.get_release(release_id)

    async def resolve_config(self, req: FrontendConfigRequest) -> dict[str, Any]:
        frontend_config_requests_total.inc()
        started = time.perf_counter()

        host = self._normalize_host(req.host)
        path = self._normalize_path(req.path)
        query = {str(k): str(v) for k, v in req.query_params.items()}

        state = await self.repo.get_runtime_state()
        if not state or not state.active_profile_id:
            raise ValueError("frontend runtime state is not configured")

        state_stamp = int(state.updated_at.timestamp()) if state.updated_at else 0
        cache_key = (
            f"frontend:cfg:{host}:{path}:{self._query_hash(query)}:"
            f"{req.sticky_release_id or 'none'}:{state.active_profile_id}:{state_stamp}"
        )
        cached = await self._cache_get(cache_key)
        if cached:
            frontend_config_resolution_latency_ms.observe((time.perf_counter() - started) * 1000.0)
            return cached

        chosen_release = None
        matched_rule_id = None
        sticky_used = False
        fallback_used = False

        if req.sticky_release_id and state.sticky_enabled:
            sticky_candidate = await self._get_release_by_id(req.sticky_release_id)
            if sticky_candidate and sticky_candidate.status in {"ready", "active"} and sticky_candidate.health_status == "healthy":
                chosen_release = sticky_candidate
                sticky_used = True

        if not chosen_release:
            rules = await self.repo.list_active_rules(state.active_profile_id)
            for rule in rules:
                host_match = fnmatch(host, rule.host_pattern or "*")
                path_match = fnmatch(path, rule.path_pattern or "/*")
                if not host_match or not path_match:
                    continue

                conditions = rule.query_conditions or {}
                is_match = True
                for cond_key, cond_value in conditions.items():
                    if query.get(str(cond_key)) != str(cond_value):
                        is_match = False
                        break
                if not is_match:
                    continue

                rel = await self._get_release_by_id(rule.target_release_id)
                if not rel:
                    continue
                if rel.status not in {"ready", "active"}:
                    continue
                if rel.health_status != "healthy":
                    continue

                chosen_release = rel
                matched_rule_id = rule.id
                break

        if not chosen_release:
            fallback_used = True
            if state.fallback_release_id:
                fallback_release = await self._get_release_by_id(state.fallback_release_id)
                if fallback_release and fallback_release.status in {"ready", "active"} and fallback_release.health_status == "healthy":
                    chosen_release = fallback_release

        if not chosen_release:
            raise ValueError("no valid release configured")

        flags = dict(chosen_release.flags or {})
        if matched_rule_id:
            rule = await self.repo.get_rule(matched_rule_id)
            if rule and isinstance(rule.flags_override, dict):
                flags = self._deep_merge(flags, rule.flags_override)

        sticky_key = f"fr_{chosen_release.id}"
        target_url = chosen_release.target_url.rstrip("/") + path
        if query:
            query_part = "&".join([f"{k}={v}" for k, v in query.items()])
            target_url = f"{target_url}?{query_part}"

        result = {
            "target_url": target_url,
            "release_id": chosen_release.id,
            "cache_ttl": int(state.cache_ttl_seconds or 15),
            "sticky_key": sticky_key,
            "flags": flags,
            "sticky_enabled": bool(state.sticky_enabled),
            "sticky_ttl_seconds": int(state.sticky_ttl_seconds or 1800),
            "matched_rule_id": matched_rule_id,
            "fallback_used": fallback_used,
            "sticky_used": sticky_used,
            "profile_id": state.active_profile_id,
        }

        if fallback_used:
            frontend_config_fallback_total.inc()

        await self._cache_set(cache_key, result, ttl=result["cache_ttl"])

        logger.info(
            "frontend_config_resolved",
            extra={
                "release_id": chosen_release.id,
                "profile_id": state.active_profile_id,
                "matched_rule_id": matched_rule_id,
                "fallback_used": fallback_used,
                "sticky_used": sticky_used,
            },
        )

        frontend_config_resolution_latency_ms.observe((time.perf_counter() - started) * 1000.0)
        return result

    async def validate_release(self, release_id: int) -> dict[str, Any]:
        release = await self.repo.get_release(release_id)
        if not release:
            raise ValueError("release not found")

        parsed = urlparse(release.target_url)
        now = datetime.now(timezone.utc)

        if parsed.scheme.lower() != "https":
            updated = await self.repo.update_release(
                release_id,
                {
                    "health_status": "unhealthy",
                    "validated_at": now,
                },
                actor_id=None,
            )
            return {
                "release_id": release_id,
                "ok": False,
                "reason": "target_url must use https",
                "status_code": None,
                "health_status": updated.health_status if updated else "unhealthy",
                "validated_at": updated.validated_at if updated else now,
            }

        hostname = (parsed.hostname or "").lower()
        if not hostname:
            updated = await self.repo.update_release(
                release_id,
                {"health_status": "unhealthy", "validated_at": now},
                actor_id=None,
            )
            return {
                "release_id": release_id,
                "ok": False,
                "reason": "target_url host is empty",
                "status_code": None,
                "health_status": updated.health_status if updated else "unhealthy",
                "validated_at": updated.validated_at if updated else now,
            }

        allowed = await self.repo.has_allowed_host(hostname)
        if not allowed:
            updated = await self.repo.update_release(
                release_id,
                {"health_status": "unhealthy", "validated_at": now},
                actor_id=None,
            )
            return {
                "release_id": release_id,
                "ok": False,
                "reason": f"host {hostname} is not in allowlist",
                "status_code": None,
                "health_status": updated.health_status if updated else "unhealthy",
                "validated_at": updated.validated_at if updated else now,
            }

        status_code = None
        ok = False
        reason = None

        async with httpx.AsyncClient(timeout=3.0, follow_redirects=True) as client:
            try:
                response = await client.head(release.target_url)
                status_code = response.status_code
                ok = status_code < 500
                if not ok:
                    response = await client.get(release.target_url)
                    status_code = response.status_code
                    ok = status_code < 500
            except Exception as exc:
                reason = str(exc)
                ok = False

        health_status = "healthy" if ok else "unhealthy"
        updated = await self.repo.update_release(
            release_id,
            {
                "health_status": health_status,
                "validated_at": now,
            },
            actor_id=None,
        )

        return {
            "release_id": release_id,
            "ok": ok,
            "reason": reason,
            "status_code": status_code,
            "health_status": updated.health_status if updated else health_status,
            "validated_at": updated.validated_at if updated else now,
        }
