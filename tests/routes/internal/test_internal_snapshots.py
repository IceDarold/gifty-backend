from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock

import pytest

from routes import internal as internal_routes


@pytest.mark.asyncio
async def test_snapshot_meta_get_set_and_read_write(fake_redis):
    assert await internal_routes._snapshot_meta_get(fake_redis) == {}
    await fake_redis.set(internal_routes.OPS_SNAPSHOT_META_KEY, "not-json", ex=10)
    assert await internal_routes._snapshot_meta_get(fake_redis) == {}

    await internal_routes._snapshot_meta_set(fake_redis, {"a": 1}, ttl_ms=2000)
    meta = await internal_routes._snapshot_meta_get(fake_redis)
    assert meta["a"] == 1

    key = "ops:snapshot:test"
    assert await internal_routes._snapshot_read(fake_redis, key) is None
    await internal_routes._snapshot_write(fake_redis, block="overview", key=key, payload={"x": 1}, ttl_ms=1000)
    cached = await internal_routes._snapshot_read(fake_redis, key)
    assert cached and cached["payload"]["x"] == 1


def test_snapshot_key_variants():
    assert internal_routes._snapshot_key("overview") == internal_routes.OPS_SNAPSHOT_OVERVIEW_KEY
    assert internal_routes._snapshot_key("scheduler_stats") == internal_routes.OPS_SNAPSHOT_SCHEDULER_STATS_KEY
    assert internal_routes._snapshot_key("items_trend", granularity="hour", buckets=10).startswith("ops:snapshot:items_trend:")
    with pytest.raises(ValueError):
        internal_routes._snapshot_key("unknown")


def test_iso_parse_and_staleness():
    now = datetime.now(timezone.utc)
    assert internal_routes._parse_iso_dt(None) is None
    assert internal_routes._parse_iso_dt("bad") is None
    assert internal_routes._iso(now).startswith(str(now.date()))

    fresh = now.isoformat()
    old = (now - timedelta(seconds=10)).isoformat()
    assert internal_routes._is_snapshot_stale(fresh, stale_max_age_ms=10000) is False
    assert internal_routes._is_snapshot_stale(old, stale_max_age_ms=1) is True


def test_add_snapshot_meta_fields():
    payload = {"status": "ok", "item": {"x": 1}}
    out = internal_routes._add_snapshot_meta_fields(payload, cache_key="k", generated_at="t", stale=False)
    assert out["status"] == "ok"
    assert out["snapshot_key"] == "k"
    assert out["stale"] is False


@pytest.mark.asyncio
async def test_trigger_snapshot_refresh_runs_compute_and_releases_lock(fake_redis):
    cache_key = "ops:snapshot:overview:v1"
    compute = AsyncMock(return_value={"x": 1})

    await internal_routes._trigger_snapshot_refresh_if_needed(
        redis=fake_redis,
        cache_key=cache_key,
        block="overview",
        ttl_ms=1000,
        compute_fn=compute,
    )

    # Let background task run.
    await asyncio.sleep(0.05)
    compute.assert_awaited()
    cached = await internal_routes._snapshot_read(fake_redis, cache_key)
    assert cached and cached["payload"]["x"] == 1
    assert await fake_redis.get(internal_routes._snapshot_refresh_lock_key(cache_key)) is None


def test_extract_categories_and_detect_error():
    logs = "Batch ingested: 10 products, 12 categories\\nBatch ingested: 1 products, 3 categories"
    assert internal_routes._extract_categories_scraped_from_logs(logs) == 15

    assert internal_routes._detect_run_error_from_logs("FAILED to ingest batch") == "Failed to ingest batch"
    assert internal_routes._detect_run_error_from_logs(None) is None
