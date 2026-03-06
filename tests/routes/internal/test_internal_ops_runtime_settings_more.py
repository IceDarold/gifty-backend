from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from routes import internal as internal_routes


@pytest.mark.anyio
async def test_update_ops_runtime_settings_redis_limiter_failure_does_not_block(fake_db, fake_redis, monkeypatch):
    state = SimpleNamespace(
        scheduler_paused=False,
        settings_version=1,
        ops_aggregator_enabled=True,
        ops_aggregator_interval_ms=2000,
        ops_snapshot_ttl_ms=10000,
        ops_stale_max_age_ms=60000,
        ops_client_intervals=dict(internal_routes.OPS_CLIENT_INTERVAL_DEFAULTS),
        updated_by=None,
        updated_at=None,
    )
    monkeypatch.setattr(internal_routes, "_get_or_create_ops_runtime_state", AsyncMock(return_value=state))
    fake_db.commit = AsyncMock()
    fake_db.refresh = AsyncMock()

    async def _boom(*a, **k):
        raise RuntimeError("redis down")

    monkeypatch.setattr(fake_redis, "set", _boom)

    req = internal_routes.OpsRuntimeSettingsUpdateRequest(ops_aggregator_enabled=False)
    out = await internal_routes.update_ops_runtime_settings(
        data=req,
        db=fake_db,
        redis=fake_redis,
        principal="tg_admin:1",
    )
    assert out["status"] == "ok"


@pytest.mark.anyio
async def test_update_ops_runtime_settings_validates_ops_client_intervals(fake_db, fake_redis, monkeypatch):
    state = SimpleNamespace(
        scheduler_paused=False,
        settings_version=1,
        ops_aggregator_enabled=True,
        ops_aggregator_interval_ms=2000,
        ops_snapshot_ttl_ms=10000,
        ops_stale_max_age_ms=60000,
        ops_client_intervals=dict(internal_routes.OPS_CLIENT_INTERVAL_DEFAULTS),
        updated_by=None,
        updated_at=None,
    )
    monkeypatch.setattr(internal_routes, "_get_or_create_ops_runtime_state", AsyncMock(return_value=state))
    fake_db.commit = AsyncMock()
    fake_db.refresh = AsyncMock()
    fake_redis.set = AsyncMock(return_value=True)

    # not an object
    req = internal_routes.OpsRuntimeSettingsUpdateRequest(ops_client_intervals=None)
    # use raw payload by constructing model_dump replacement: easiest call route with incorrect dict via model directly isn't possible
    bad = SimpleNamespace(model_dump=lambda exclude_unset=True: {"ops_client_intervals": "x"})
    with pytest.raises(internal_routes.HTTPException) as exc:
        await internal_routes.update_ops_runtime_settings(data=bad, db=fake_db, redis=fake_redis, principal="internal")
    assert exc.value.status_code == 400

    # unknown key
    bad2 = SimpleNamespace(model_dump=lambda exclude_unset=True: {"ops_client_intervals": {"unknown": 1000}})
    with pytest.raises(internal_routes.HTTPException) as exc2:
        await internal_routes.update_ops_runtime_settings(data=bad2, db=fake_db, redis=fake_redis, principal="internal")
    assert exc2.value.status_code == 400

    # invalid int
    key = next(iter(internal_routes.OPS_CLIENT_INTERVAL_DEFAULTS.keys()))
    bad3 = SimpleNamespace(model_dump=lambda exclude_unset=True: {"ops_client_intervals": {key: "nope"}})
    with pytest.raises(internal_routes.HTTPException) as exc3:
        await internal_routes.update_ops_runtime_settings(data=bad3, db=fake_db, redis=fake_redis, principal="internal")
    assert exc3.value.status_code == 400

    # happy path merges and bumps version
    good = SimpleNamespace(model_dump=lambda exclude_unset=True: {"ops_client_intervals": {key: 2000}})
    out = await internal_routes.update_ops_runtime_settings(data=good, db=fake_db, redis=fake_redis, principal="tg_admin:9")
    assert out["status"] == "ok"
    assert out["item"]["ops_client_intervals"][key] == 2000
    assert state.settings_version == 2
    assert state.updated_by == 9
    assert isinstance(state.updated_at, datetime)
