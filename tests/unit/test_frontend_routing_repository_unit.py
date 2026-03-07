from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.repositories.frontend_routing import FrontendRoutingRepository


@dataclass
class _ScalarsResult:
    items: list

    def scalars(self):
        return SimpleNamespace(all=lambda: list(self.items))


@dataclass
class _ScalarOneOrNoneResult:
    value: object

    def scalar_one_or_none(self):
        return self.value


@pytest.mark.anyio
async def test_frontend_routing_repository_crud_and_ops_smoke(monkeypatch):
    session = AsyncMock()
    session.add = lambda _obj: None
    session.delete = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    repo = FrontendRoutingRepository(session)

    # list/get apps
    session.execute = AsyncMock(side_effect=[_ScalarsResult([SimpleNamespace(id=1)]), _ScalarOneOrNoneResult(None)])
    assert (await repo.list_apps())[0].id == 1
    assert await repo.get_app(123) is None

    # create/update/delete app (audit path)
    app = SimpleNamespace(id=10, key="k", name="n", is_active=True)
    repo.get_app = AsyncMock(return_value=app)
    created = await repo.create_app({"key": "k", "name": "n", "is_active": True}, actor_id=1)
    assert created.key == "k"

    updated = await repo.update_app(10, {"name": "n2"}, actor_id=2)
    assert updated.name == "n2"

    ok = await repo.delete_app(10, actor_id=3)
    assert ok is True

    repo.get_app = AsyncMock(return_value=None)
    assert await repo.update_app(999, {"name": "x"}, actor_id=1) is None
    assert await repo.delete_app(999, actor_id=1) is False

    # releases list/get/update/delete branches
    rel = SimpleNamespace(id=20, app_id=10, version="1", target_url="u", status="draft", health_status="unknown", flags={})
    session.execute = AsyncMock(side_effect=[_ScalarsResult([rel]), _ScalarOneOrNoneResult(rel)])
    assert (await repo.list_releases(app_id=10))[0].id == 20
    assert (await repo.get_release(20)).id == 20

    repo.get_release = AsyncMock(return_value=rel)
    assert (await repo.update_release(20, {"status": "ready"}, actor_id=1)).status == "ready"
    assert await repo.delete_release(20, actor_id=1) is True

    repo.get_release = AsyncMock(return_value=None)
    assert await repo.update_release(999, {"status": "x"}, actor_id=1) is None
    assert await repo.delete_release(999, actor_id=1) is False

    # profiles/rules
    prof = SimpleNamespace(id=30, key="p", name="P", is_active=True)
    repo.get_profile = AsyncMock(return_value=prof)
    assert (await repo.update_profile(30, {"is_active": False}, actor_id=1)).is_active is False
    repo.get_profile = AsyncMock(return_value=None)
    assert await repo.update_profile(999, {"name": "x"}, actor_id=1) is None

    rule = SimpleNamespace(
        id=40,
        profile_id=30,
        priority=10,
        host_pattern="*",
        path_pattern="/*",
        query_conditions={},
        target_release_id=20,
        flags_override={},
        is_active=True,
    )
    repo.get_rule = AsyncMock(return_value=rule)
    assert (await repo.update_rule(40, {"priority": 1}, actor_id=1)).priority == 1
    assert await repo.delete_rule(40, actor_id=1) is True
    repo.get_rule = AsyncMock(return_value=None)
    assert await repo.update_rule(999, {"priority": 1}, actor_id=1) is None
    assert await repo.delete_rule(999, actor_id=1) is False

    # runtime state set/publish/rollback
    state = SimpleNamespace(
        id=1,
        active_profile_id=None,
        fallback_release_id=None,
        sticky_enabled=False,
        sticky_ttl_seconds=0,
        cache_ttl_seconds=0,
        updated_by=None,
        updated_at=None,
    )
    repo.get_runtime_state = AsyncMock(return_value=None)
    created_state = await repo.set_runtime_state({"active_profile_id": 30, "fallback_release_id": 20}, actor_id=7)
    assert created_state.id == 1

    repo.get_runtime_state = AsyncMock(return_value=state)
    published = await repo.publish(
        active_profile_id=30,
        fallback_release_id=20,
        actor_id=7,
        sticky_enabled=True,
        sticky_ttl_seconds=60,
        cache_ttl_seconds=10,
    )
    assert published.sticky_enabled is True

    repo.get_latest_stable_release = AsyncMock(return_value=SimpleNamespace(id=21))
    rolled = await repo.rollback(actor_id=7, app_id=10)
    assert rolled.fallback_release_id == 21

    repo.get_runtime_state = AsyncMock(return_value=None)
    assert await repo.rollback(actor_id=7, app_id=10) is None


@pytest.mark.anyio
async def test_frontend_routing_repository_lists_and_allowed_hosts_and_queries():
    session = AsyncMock()
    session.add = lambda _obj: None
    session.delete = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    repo = FrontendRoutingRepository(session)

    # profiles and rules listing
    prof = SimpleNamespace(id=1)
    rule = SimpleNamespace(id=2)
    session.execute = AsyncMock(side_effect=[_ScalarsResult([prof]), _ScalarsResult([rule]), _ScalarsResult([rule])])
    assert (await repo.list_profiles())[0].id == 1
    assert (await repo.list_rules(profile_id=1))[0].id == 2
    assert (await repo.list_active_rules(profile_id=1))[0].id == 2

    # create_profile/create_rule/create_release smoke
    created_profile = await repo.create_profile({"key": "p", "name": "P", "is_active": True}, actor_id=1)
    assert created_profile.key == "p"

    created_release = await repo.create_release(
        {"app_id": 1, "version": "1", "target_url": "u", "status": "draft", "health_status": "unknown", "flags": {}},
        actor_id=1,
    )
    assert created_release.version == "1"

    created_rule = await repo.create_rule(
        {
            "profile_id": 1,
            "priority": 10,
            "host_pattern": "*",
            "path_pattern": "/*",
            "query_conditions": {},
            "target_release_id": 1,
            "flags_override": {},
            "is_active": True,
        },
        actor_id=1,
    )
    assert created_rule.priority == 10

    # allowed hosts: list/get/has/create/update/delete
    host = SimpleNamespace(id=5, host="example.com", is_active=True)
    session.execute = AsyncMock(
        side_effect=[
            _ScalarsResult([host]),  # list_allowed_hosts
            _ScalarOneOrNoneResult(host),  # get_allowed_host
            _ScalarOneOrNoneResult(1),  # has_allowed_host true
        ]
    )
    assert (await repo.list_allowed_hosts())[0].id == 5
    assert (await repo.get_allowed_host(5)).host == "example.com"
    assert await repo.has_allowed_host("Example.COM") is True

    created = await repo.create_allowed_host({"host": "Example.COM", "is_active": True}, actor_id=1)
    assert created.host == "example.com"

    repo.get_allowed_host = AsyncMock(return_value=host)
    updated = await repo.update_allowed_host(5, {"host": "X.COM", "is_active": False}, actor_id=2)
    assert updated.host == "x.com"
    assert updated.is_active is False

    repo.get_allowed_host = AsyncMock(return_value=None)
    assert await repo.update_allowed_host(999, {"host": "x"}, actor_id=1) is None
    assert await repo.delete_allowed_host(999, actor_id=1) is False

    repo.get_allowed_host = AsyncMock(return_value=host)
    assert await repo.delete_allowed_host(5, actor_id=1) is True

    # audit log listing
    session.execute = AsyncMock(return_value=_ScalarsResult([SimpleNamespace(id=1)]))
    assert (await repo.list_audit_log(limit=1, offset=0))[0].id == 1

    # stable release query branches
    session.execute = AsyncMock(return_value=_ScalarOneOrNoneResult(SimpleNamespace(id=7)))
    assert (await repo.get_latest_stable_release(app_id=1, exclude_release_id=2)).id == 7
