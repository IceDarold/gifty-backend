from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    FrontendAllowedHost,
    FrontendApp,
    FrontendAuditLog,
    FrontendProfile,
    FrontendRelease,
    FrontendRule,
    FrontendRuntimeState,
)


class FrontendRoutingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _audit(
        self,
        *,
        actor_id: Optional[int],
        action: str,
        entity_type: str,
        entity_id: Optional[str] = None,
        before: Optional[dict[str, Any]] = None,
        after: Optional[dict[str, Any]] = None,
    ) -> FrontendAuditLog:
        row = FrontendAuditLog(
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=before,
            after=after,
        )
        self.session.add(row)
        return row

    async def list_apps(self) -> Sequence[FrontendApp]:
        result = await self.session.execute(select(FrontendApp).order_by(FrontendApp.id.asc()))
        return result.scalars().all()

    async def get_app(self, app_id: int) -> Optional[FrontendApp]:
        result = await self.session.execute(select(FrontendApp).where(FrontendApp.id == app_id))
        return result.scalar_one_or_none()

    async def create_app(self, payload: dict[str, Any], actor_id: Optional[int]) -> FrontendApp:
        row = FrontendApp(**payload)
        self.session.add(row)
        await self.session.flush()
        await self._audit(actor_id=actor_id, action="create", entity_type="frontend_app", entity_id=str(row.id), after=payload)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def update_app(self, app_id: int, payload: dict[str, Any], actor_id: Optional[int]) -> Optional[FrontendApp]:
        row = await self.get_app(app_id)
        if not row:
            return None
        before = {"key": row.key, "name": row.name, "is_active": row.is_active}
        for key, value in payload.items():
            setattr(row, key, value)
        await self._audit(actor_id=actor_id, action="update", entity_type="frontend_app", entity_id=str(row.id), before=before, after=payload)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def delete_app(self, app_id: int, actor_id: Optional[int]) -> bool:
        row = await self.get_app(app_id)
        if not row:
            return False
        before = {"id": row.id, "key": row.key, "name": row.name, "is_active": row.is_active}
        await self.session.delete(row)
        await self._audit(actor_id=actor_id, action="delete", entity_type="frontend_app", entity_id=str(app_id), before=before)
        await self.session.commit()
        return True

    async def list_releases(self, app_id: Optional[int] = None) -> Sequence[FrontendRelease]:
        stmt = select(FrontendRelease)
        if app_id is not None:
            stmt = stmt.where(FrontendRelease.app_id == app_id)
        stmt = stmt.order_by(FrontendRelease.id.desc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_release(self, release_id: int) -> Optional[FrontendRelease]:
        result = await self.session.execute(select(FrontendRelease).where(FrontendRelease.id == release_id))
        return result.scalar_one_or_none()

    async def create_release(self, payload: dict[str, Any], actor_id: Optional[int]) -> FrontendRelease:
        row = FrontendRelease(**payload)
        self.session.add(row)
        await self.session.flush()
        await self._audit(actor_id=actor_id, action="create", entity_type="frontend_release", entity_id=str(row.id), after=payload)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def update_release(self, release_id: int, payload: dict[str, Any], actor_id: Optional[int]) -> Optional[FrontendRelease]:
        row = await self.get_release(release_id)
        if not row:
            return None
        before = {
            "version": row.version,
            "target_url": row.target_url,
            "status": row.status,
            "health_status": row.health_status,
            "flags": row.flags,
        }
        for key, value in payload.items():
            setattr(row, key, value)
        await self._audit(actor_id=actor_id, action="update", entity_type="frontend_release", entity_id=str(row.id), before=before, after=payload)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def delete_release(self, release_id: int, actor_id: Optional[int]) -> bool:
        row = await self.get_release(release_id)
        if not row:
            return False
        before = {
            "id": row.id,
            "app_id": row.app_id,
            "version": row.version,
            "status": row.status,
            "target_url": row.target_url,
        }
        await self.session.delete(row)
        await self._audit(actor_id=actor_id, action="delete", entity_type="frontend_release", entity_id=str(release_id), before=before)
        await self.session.commit()
        return True

    async def list_profiles(self) -> Sequence[FrontendProfile]:
        result = await self.session.execute(select(FrontendProfile).order_by(FrontendProfile.id.asc()))
        return result.scalars().all()

    async def get_profile(self, profile_id: int) -> Optional[FrontendProfile]:
        result = await self.session.execute(select(FrontendProfile).where(FrontendProfile.id == profile_id))
        return result.scalar_one_or_none()

    async def create_profile(self, payload: dict[str, Any], actor_id: Optional[int]) -> FrontendProfile:
        row = FrontendProfile(**payload)
        self.session.add(row)
        await self.session.flush()
        await self._audit(actor_id=actor_id, action="create", entity_type="frontend_profile", entity_id=str(row.id), after=payload)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def update_profile(self, profile_id: int, payload: dict[str, Any], actor_id: Optional[int]) -> Optional[FrontendProfile]:
        row = await self.get_profile(profile_id)
        if not row:
            return None
        before = {"key": row.key, "name": row.name, "is_active": row.is_active}
        for key, value in payload.items():
            setattr(row, key, value)
        await self._audit(actor_id=actor_id, action="update", entity_type="frontend_profile", entity_id=str(row.id), before=before, after=payload)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def list_rules(self, profile_id: Optional[int] = None) -> Sequence[FrontendRule]:
        stmt = select(FrontendRule)
        if profile_id is not None:
            stmt = stmt.where(FrontendRule.profile_id == profile_id)
        stmt = stmt.order_by(FrontendRule.priority.desc(), FrontendRule.id.asc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_rule(self, rule_id: int) -> Optional[FrontendRule]:
        result = await self.session.execute(select(FrontendRule).where(FrontendRule.id == rule_id))
        return result.scalar_one_or_none()

    async def create_rule(self, payload: dict[str, Any], actor_id: Optional[int]) -> FrontendRule:
        row = FrontendRule(**payload)
        self.session.add(row)
        await self.session.flush()
        await self._audit(actor_id=actor_id, action="create", entity_type="frontend_rule", entity_id=str(row.id), after=payload)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def update_rule(self, rule_id: int, payload: dict[str, Any], actor_id: Optional[int]) -> Optional[FrontendRule]:
        row = await self.get_rule(rule_id)
        if not row:
            return None
        before = {
            "priority": row.priority,
            "host_pattern": row.host_pattern,
            "path_pattern": row.path_pattern,
            "query_conditions": row.query_conditions,
            "target_release_id": row.target_release_id,
            "flags_override": row.flags_override,
            "is_active": row.is_active,
        }
        for key, value in payload.items():
            setattr(row, key, value)
        await self._audit(actor_id=actor_id, action="update", entity_type="frontend_rule", entity_id=str(row.id), before=before, after=payload)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def delete_rule(self, rule_id: int, actor_id: Optional[int]) -> bool:
        row = await self.get_rule(rule_id)
        if not row:
            return False
        before = {
            "id": row.id,
            "profile_id": row.profile_id,
            "priority": row.priority,
            "host_pattern": row.host_pattern,
            "path_pattern": row.path_pattern,
            "target_release_id": row.target_release_id,
            "is_active": row.is_active,
        }
        await self.session.delete(row)
        await self._audit(actor_id=actor_id, action="delete", entity_type="frontend_rule", entity_id=str(rule_id), before=before)
        await self.session.commit()
        return True

    async def get_runtime_state(self) -> Optional[FrontendRuntimeState]:
        result = await self.session.execute(select(FrontendRuntimeState).where(FrontendRuntimeState.id == 1))
        return result.scalar_one_or_none()

    async def set_runtime_state(self, payload: dict[str, Any], actor_id: Optional[int]) -> FrontendRuntimeState:
        state = await self.get_runtime_state()
        if not state:
            state = FrontendRuntimeState(id=1)
            self.session.add(state)
            await self.session.flush()

        before = {
            "active_profile_id": state.active_profile_id,
            "fallback_release_id": state.fallback_release_id,
            "sticky_enabled": state.sticky_enabled,
            "sticky_ttl_seconds": state.sticky_ttl_seconds,
            "cache_ttl_seconds": state.cache_ttl_seconds,
            "updated_by": state.updated_by,
        }
        for key, value in payload.items():
            setattr(state, key, value)
        state.updated_by = actor_id
        state.updated_at = datetime.now(timezone.utc)

        await self._audit(actor_id=actor_id, action="update", entity_type="frontend_runtime_state", entity_id="1", before=before, after=payload)
        await self.session.commit()
        await self.session.refresh(state)
        return state

    async def list_allowed_hosts(self) -> Sequence[FrontendAllowedHost]:
        result = await self.session.execute(select(FrontendAllowedHost).order_by(FrontendAllowedHost.id.asc()))
        return result.scalars().all()

    async def get_allowed_host(self, host_id: int) -> Optional[FrontendAllowedHost]:
        result = await self.session.execute(select(FrontendAllowedHost).where(FrontendAllowedHost.id == host_id))
        return result.scalar_one_or_none()

    async def has_allowed_host(self, host: str) -> bool:
        result = await self.session.execute(
            select(FrontendAllowedHost.id).where(
                FrontendAllowedHost.host == host.lower(),
                FrontendAllowedHost.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none() is not None

    async def create_allowed_host(self, payload: dict[str, Any], actor_id: Optional[int]) -> FrontendAllowedHost:
        payload = dict(payload)
        payload["host"] = payload["host"].lower()
        row = FrontendAllowedHost(**payload)
        self.session.add(row)
        await self.session.flush()
        await self._audit(actor_id=actor_id, action="create", entity_type="frontend_allowed_host", entity_id=str(row.id), after=payload)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def update_allowed_host(self, host_id: int, payload: dict[str, Any], actor_id: Optional[int]) -> Optional[FrontendAllowedHost]:
        row = await self.get_allowed_host(host_id)
        if not row:
            return None
        before = {"host": row.host, "is_active": row.is_active}
        payload = dict(payload)
        if "host" in payload:
            payload["host"] = payload["host"].lower()
        for key, value in payload.items():
            setattr(row, key, value)
        await self._audit(actor_id=actor_id, action="update", entity_type="frontend_allowed_host", entity_id=str(row.id), before=before, after=payload)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def delete_allowed_host(self, host_id: int, actor_id: Optional[int]) -> bool:
        row = await self.get_allowed_host(host_id)
        if not row:
            return False
        before = {"id": row.id, "host": row.host, "is_active": row.is_active}
        await self.session.delete(row)
        await self._audit(actor_id=actor_id, action="delete", entity_type="frontend_allowed_host", entity_id=str(host_id), before=before)
        await self.session.commit()
        return True

    async def list_audit_log(self, limit: int = 100, offset: int = 0) -> Sequence[FrontendAuditLog]:
        result = await self.session.execute(
            select(FrontendAuditLog)
            .order_by(FrontendAuditLog.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()

    async def list_active_rules(self, profile_id: int) -> Sequence[FrontendRule]:
        result = await self.session.execute(
            select(FrontendRule)
            .where(FrontendRule.profile_id == profile_id, FrontendRule.is_active.is_(True))
            .order_by(FrontendRule.priority.desc(), FrontendRule.id.asc())
        )
        return result.scalars().all()

    async def get_latest_stable_release(self, app_id: Optional[int] = None, exclude_release_id: Optional[int] = None) -> Optional[FrontendRelease]:
        stmt = select(FrontendRelease).where(
            FrontendRelease.status.in_(["ready", "active"]),
            FrontendRelease.health_status == "healthy",
        )
        if app_id is not None:
            stmt = stmt.where(FrontendRelease.app_id == app_id)
        if exclude_release_id is not None:
            stmt = stmt.where(FrontendRelease.id != exclude_release_id)
        stmt = stmt.order_by(FrontendRelease.validated_at.desc().nullslast(), FrontendRelease.id.desc())
        result = await self.session.execute(stmt.limit(1))
        return result.scalar_one_or_none()

    async def publish(
        self,
        *,
        active_profile_id: int,
        fallback_release_id: int,
        actor_id: Optional[int],
        sticky_enabled: Optional[bool] = None,
        sticky_ttl_seconds: Optional[int] = None,
        cache_ttl_seconds: Optional[int] = None,
    ) -> FrontendRuntimeState:
        state = await self.get_runtime_state()
        if not state:
            state = FrontendRuntimeState(id=1)
            self.session.add(state)
            await self.session.flush()

        before = {
            "active_profile_id": state.active_profile_id,
            "fallback_release_id": state.fallback_release_id,
            "sticky_enabled": state.sticky_enabled,
            "sticky_ttl_seconds": state.sticky_ttl_seconds,
            "cache_ttl_seconds": state.cache_ttl_seconds,
        }

        state.active_profile_id = active_profile_id
        state.fallback_release_id = fallback_release_id
        if sticky_enabled is not None:
            state.sticky_enabled = sticky_enabled
        if sticky_ttl_seconds is not None:
            state.sticky_ttl_seconds = sticky_ttl_seconds
        if cache_ttl_seconds is not None:
            state.cache_ttl_seconds = cache_ttl_seconds
        state.updated_by = actor_id
        state.updated_at = datetime.now(timezone.utc)

        await self._audit(
            actor_id=actor_id,
            action="publish",
            entity_type="frontend_runtime_state",
            entity_id="1",
            before=before,
            after={
                "active_profile_id": state.active_profile_id,
                "fallback_release_id": state.fallback_release_id,
                "sticky_enabled": state.sticky_enabled,
                "sticky_ttl_seconds": state.sticky_ttl_seconds,
                "cache_ttl_seconds": state.cache_ttl_seconds,
            },
        )
        await self.session.commit()
        await self.session.refresh(state)
        return state

    async def rollback(self, *, actor_id: Optional[int], app_id: Optional[int] = None) -> Optional[FrontendRuntimeState]:
        state = await self.get_runtime_state()
        if not state:
            return None

        candidate = await self.get_latest_stable_release(app_id=app_id, exclude_release_id=state.fallback_release_id)
        if not candidate:
            return None

        before = {
            "fallback_release_id": state.fallback_release_id,
            "active_profile_id": state.active_profile_id,
        }

        state.fallback_release_id = candidate.id
        state.updated_by = actor_id
        state.updated_at = datetime.now(timezone.utc)

        await self._audit(
            actor_id=actor_id,
            action="rollback",
            entity_type="frontend_runtime_state",
            entity_id="1",
            before=before,
            after={
                "fallback_release_id": state.fallback_release_id,
                "active_profile_id": state.active_profile_id,
            },
        )
        await self.session.commit()
        await self.session.refresh(state)
        return state
