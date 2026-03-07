from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from routes import internal as internal_routes


def test_normalize_client_intervals_defaults_on_bad_input():
    assert internal_routes._normalize_client_intervals(None) == internal_routes.OPS_CLIENT_INTERVAL_DEFAULTS
    assert internal_routes._normalize_client_intervals("nope") == internal_routes.OPS_CLIENT_INTERVAL_DEFAULTS


def test_normalize_client_intervals_filters_and_clamps():
    raw = {
        "ops.overview_ms": "1000",
        "ops.sites_ms": "not-a-number",
        "unknown.key": 123,
        "dashboard.queue_stats_ms": 999999999,  # out of bounds
    }
    normalized = internal_routes._normalize_client_intervals(raw)
    assert normalized["ops.overview_ms"] == 1000
    assert "unknown.key" not in normalized
    assert normalized["dashboard.queue_stats_ms"] == internal_routes.OPS_CLIENT_INTERVAL_DEFAULTS["dashboard.queue_stats_ms"]
    # invalid int conversion keeps default
    assert normalized["ops.sites_ms"] == internal_routes.OPS_CLIENT_INTERVAL_DEFAULTS["ops.sites_ms"]


def test_extract_site_name_from_config():
    assert internal_routes._extract_site_name_from_config(None) is None
    assert internal_routes._extract_site_name_from_config("x") is None
    assert internal_routes._extract_site_name_from_config({}) is None
    assert internal_routes._extract_site_name_from_config({"name": "  MrGeek  "}) == "MrGeek"
    assert internal_routes._extract_site_name_from_config({"site_title": "T"}) == "T"


def test_serialize_ops_runtime_settings_defaults_and_types():
    state = SimpleNamespace(
        scheduler_paused=False,
        settings_version=None,
        ops_aggregator_enabled=True,
        ops_aggregator_interval_ms=None,
        ops_snapshot_ttl_ms=None,
        ops_stale_max_age_ms=None,
        ops_client_intervals=None,
        updated_by=None,
        updated_at=None,
    )
    payload = internal_routes._serialize_ops_runtime_settings(state)
    assert payload["status"] == "ok"
    assert payload["item"]["ops_aggregator_interval_ms"] == 2000
    assert isinstance(payload["item"]["ops_client_intervals"], dict)


def test_ops_actor_id_from_principal_handles_non_int():
    assert internal_routes._ops_actor_id_from_principal("tg_admin:123") == 123
    assert internal_routes._ops_actor_id_from_principal("tg_admin:notint") is None
    assert internal_routes._ops_actor_id_from_principal("internal") is None


@pytest.mark.anyio
async def test_get_or_create_ops_runtime_state_normalizes_existing(fake_db):
    state = SimpleNamespace(
        id=1,
        scheduler_paused=False,
        settings_version=1,
        ops_aggregator_enabled=True,
        ops_aggregator_interval_ms=2000,
        ops_snapshot_ttl_ms=10000,
        ops_stale_max_age_ms=60000,
        ops_client_intervals={"ops.overview_ms": "1000", "unknown": 1},
        updated_by=None,
        updated_at=None,
    )
    fake_db.get = AsyncMock(return_value=state)
    await internal_routes._get_or_create_ops_runtime_state(fake_db)
    # commit/refresh are called when normalization changes payload
    fake_db.commit.assert_awaited()
    fake_db.refresh.assert_awaited()


class _ScalarOneOrNoneResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


@pytest.mark.anyio
async def test_sync_hub_from_hub_source_noop_for_non_hub(fake_db):
    src = SimpleNamespace(
        type="list",
        site_key="site",
        url="u",
        status="waiting",
        is_active=True,
        refresh_interval_hours=24,
        strategy=None,
        config={},
    )
    await internal_routes._sync_hub_from_hub_source(fake_db, src)
    fake_db.execute.assert_not_awaited()


@pytest.mark.anyio
async def test_sync_hub_from_hub_source_updates_existing_hub(fake_db):
    hub = SimpleNamespace(
        site_key="site",
        url="old",
        status="waiting",
        is_active=False,
        refresh_interval_hours=12,
        strategy="discovery",
        name="Old",
    )
    src = SimpleNamespace(
        type="hub",
        site_key="site",
        url="new-url",
        status="running",
        is_active=True,
        refresh_interval_hours=36,
        strategy="deep",
        config={"site_name": "  New Name  "},
    )

    fake_db.execute = AsyncMock(return_value=_ScalarOneOrNoneResult(hub))
    await internal_routes._sync_hub_from_hub_source(fake_db, src)

    assert hub.url == "new-url"
    assert hub.status == "running"
    assert hub.is_active is True
    assert hub.refresh_interval_hours == 36
    assert hub.strategy == "deep"
    assert hub.name == "New Name"
