from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import FrontendAuditLog, FrontendRuntimeState
from app.repositories.frontend_routing import FrontendRoutingRepository


@pytest.mark.asyncio
async def test_frontend_routing_crud_and_audit(postgres_session):
    repo = FrontendRoutingRepository(postgres_session)

    app = await repo.create_app({"key": "web", "name": "Web"}, actor_id=1)
    assert app.id

    app2 = await repo.update_app(app.id, {"name": "Web v2"}, actor_id=2)
    assert app2 is not None
    assert app2.name == "Web v2"

    rel = await repo.create_release(
        {
            "app_id": app.id,
            "version": "1.0.0",
            "target_url": "https://example.com/release/1",
            "status": "active",
            "health_status": "ok",
            "flags": {},
        },
        actor_id=1,
    )
    assert rel.id

    profile = await repo.create_profile({"key": "default", "name": "Default"}, actor_id=1)
    assert profile.id

    rule = await repo.create_rule(
        {
            "profile_id": profile.id,
            "priority": 100,
            "host_pattern": "*",
            "path_pattern": "/*",
            "query_conditions": {},
            "target_release_id": rel.id,
            "flags_override": {},
            "is_active": True,
        },
        actor_id=1,
    )
    assert rule.id

    # runtime state + audit
    state = await repo.set_runtime_state(
        {
            "active_profile_id": profile.id,
            "fallback_release_id": rel.id,
            "sticky_enabled": True,
            "sticky_ttl_seconds": 10,
            "cache_ttl_seconds": 1,
        },
        actor_id=123,
    )
    assert state.id == 1
    assert state.updated_by == 123

    stored_state = (await postgres_session.execute(select(FrontendRuntimeState).where(FrontendRuntimeState.id == 1))).scalar_one()
    assert stored_state.active_profile_id == profile.id

    audits = (await postgres_session.execute(select(FrontendAuditLog).order_by(FrontendAuditLog.id.asc()))).scalars().all()
    assert any(a.entity_type == "frontend_runtime_state" and a.action == "update" for a in audits)

    # delete
    ok = await repo.delete_rule(rule.id, actor_id=1)
    assert ok is True
    ok2 = await repo.delete_release(rel.id, actor_id=1)
    assert ok2 is True
    ok3 = await repo.delete_app(app.id, actor_id=1)
    assert ok3 is True


@pytest.mark.asyncio
async def test_frontend_routing_additional_paths(postgres_session):
    repo = FrontendRoutingRepository(postgres_session)

    assert await repo.list_apps() == []
    assert await repo.get_app(9999) is None
    assert await repo.update_app(9999, {"name": "x"}, actor_id=1) is None
    assert await repo.delete_app(9999, actor_id=1) is False

    app = await repo.create_app({"key": "web", "name": "Web", "is_active": True}, actor_id=1)
    assert (await repo.list_apps())[0].id == app.id
    assert (await repo.get_app(app.id)).key == "web"

    rel1 = await repo.create_release(
        {
            "app_id": app.id,
            "version": "1.0.0",
            "target_url": "https://example.com/r1",
            "status": "active",
            "health_status": "healthy",
            "flags": {},
        },
        actor_id=1,
    )
    rel2 = await repo.create_release(
        {
            "app_id": app.id,
            "version": "1.0.1",
            "target_url": "https://example.com/r2",
            "status": "ready",
            "health_status": "healthy",
            "flags": {},
        },
        actor_id=1,
    )
    assert await repo.get_release(rel1.id) is not None
    assert await repo.update_release(9999, {"status": "x"}, actor_id=1) is None
    assert await repo.delete_release(9999, actor_id=1) is False
    updated = await repo.update_release(rel2.id, {"status": "active", "health_status": "healthy"}, actor_id=9)
    assert updated is not None
    assert updated.status == "active"
    assert len(await repo.list_releases(app_id=app.id)) >= 2

    profile = await repo.create_profile({"key": "default", "name": "Default"}, actor_id=1)
    assert await repo.get_profile(profile.id) is not None
    assert await repo.update_profile(9999, {"name": "x"}, actor_id=1) is None
    prof2 = await repo.update_profile(profile.id, {"name": "Default v2", "is_active": False}, actor_id=2)
    assert prof2 is not None
    assert prof2.name == "Default v2"
    assert len(await repo.list_profiles()) == 1

    rule = await repo.create_rule(
        {
            "profile_id": profile.id,
            "priority": 10,
            "host_pattern": "*",
            "path_pattern": "/*",
            "query_conditions": {},
            "target_release_id": rel1.id,
            "flags_override": {"a": 1},
            "is_active": True,
        },
        actor_id=1,
    )
    assert await repo.get_rule(rule.id) is not None
    assert await repo.update_rule(9999, {"priority": 1}, actor_id=1) is None
    rule2 = await repo.update_rule(rule.id, {"priority": 5, "host_pattern": "x"}, actor_id=2)
    assert rule2 is not None
    assert rule2.priority == 5
    assert len(await repo.list_rules(profile_id=profile.id)) == 1
    assert len(await repo.list_active_rules(profile.id)) == 1

    # allowed hosts
    assert await repo.has_allowed_host("example.com") is False
    host = await repo.create_allowed_host({"host": "example.com"}, actor_id=1)
    assert (await repo.get_allowed_host(host.id)).host == "example.com"
    assert await repo.has_allowed_host("example.com") is True
    assert await repo.update_allowed_host(9999, {"host": "x"}, actor_id=1) is None
    host2 = await repo.update_allowed_host(host.id, {"host": "Example.COM", "is_active": False}, actor_id=2)
    assert host2 is not None
    assert host2.host == "example.com"
    assert len(await repo.list_allowed_hosts()) == 1
    assert await repo.delete_allowed_host(9999, actor_id=1) is False
    assert await repo.delete_allowed_host(host.id, actor_id=3) is True

    # runtime state helpers
    latest = await repo.get_latest_stable_release(app_id=app.id)
    assert latest is not None

    published = await repo.publish(
        active_profile_id=profile.id,
        fallback_release_id=rel1.id,
        actor_id=7,
        sticky_enabled=True,
        sticky_ttl_seconds=60,
        cache_ttl_seconds=10,
    )
    assert published.active_profile_id == profile.id
    assert published.fallback_release_id == rel1.id

    rolled = await repo.rollback(actor_id=7, app_id=app.id)
    assert rolled is not None
    assert rolled.fallback_release_id in {rel1.id, rel2.id}

    # audit log listing
    audits = await repo.list_audit_log(limit=10, offset=0)
    assert audits
