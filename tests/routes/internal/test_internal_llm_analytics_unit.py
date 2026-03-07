from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from routes import internal as internal_routes


class _OneResult:
    def __init__(self, one):
        self._one = one

    def one(self):
        return self._one


class _AllResult:
    def __init__(self, rows):
        self._rows = list(rows)

    def all(self):
        return list(self._rows)


class _ScalarOneResult:
    def __init__(self, value):
        self._value = value

    def scalar_one(self):
        return self._value


class _ScalarsAllResult:
    def __init__(self, items):
        self._items = list(items)

    def scalars(self):
        return SimpleNamespace(all=lambda: list(self._items))


class _Row:
    def __init__(self, mapping: dict):
        self._mapping = mapping


@pytest.mark.anyio
async def test_internal_intelligence_stats_converts_decimals(fake_db):
    metrics = SimpleNamespace(
        total_requests=2,
        total_cost=Decimal("1.23"),
        total_tokens=10,
        avg_latency=Decimal("45.6"),
    )
    providers_rows = [SimpleNamespace(provider="openai", count=2, cost=Decimal("1.23"))]
    latency_rows = [SimpleNamespace(hour=1, avg_latency=Decimal("12.3"))]

    fake_db.execute = AsyncMock(
        side_effect=[
            _OneResult(metrics),
            _AllResult(providers_rows),
            _AllResult(latency_rows),
        ]
    )

    out = await internal_routes.get_intelligence_stats(days=1, db=fake_db, _="internal")
    assert out["metrics"]["total_cost"] == 1.23
    assert out["metrics"]["avg_latency"] == 45.6
    assert out["providers"][0]["cost"] == 1.23
    assert out["latency_heatmap"][0]["avg_latency"] == 12.3


@pytest.mark.anyio
async def test_internal_llm_logs_clamps_and_serializes_decimals(fake_db):
    fake_redis = AsyncMock()
    fake_redis.get.return_value = None

    log = _Row(
        {
            "id": "1",
            "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
            "provider": "p",
            "model": "m",
            "call_type": "c",
            "status": "ok",
            "error_type": None,
            "error_message": None,
            "provider_request_id": None,
            "prompt_hash": "h",
            "params": {"k": "v"},
            "cost_usd": Decimal("0.12"),
            "total_tokens": 3,
            "prompt_tokens": 1,
            "completion_tokens": 2,
            "latency_ms": 10,
            "session_id": "s",
            "experiment_id": None,
            "variant_id": None,
        }
    )

    fake_db.execute = AsyncMock(
        side_effect=[
            _ScalarOneResult(1),  # total
            _AllResult([log]),  # rows
        ]
    )
    out = await internal_routes.get_llm_logs(
        days=0,
        limit=999,
        offset=-5,
        include_total=True,
        provider="p",
        model="m",
        call_type="c",
        status="ok",
        session_id="s",
        experiment_id="e",
        variant_id="v",
        db=fake_db,
        redis=fake_redis,
        _="internal",
    )
    assert out["total"] == 1
    assert out["limit"] == 200
    assert out["offset"] == 0
    assert out["items"][0]["cost_usd"] == 0.12
    assert out["items"][0]["usage_captured"] is True


@pytest.mark.anyio
async def test_internal_llm_throughput_and_breakdown(fake_db):
    fake_redis = AsyncMock()
    fake_redis.get.return_value = None

    ts = datetime(2025, 1, 1, tzinfo=timezone.utc)
    fake_db.execute = AsyncMock(
        side_effect=[
            _AllResult([SimpleNamespace(ts=ts, count=3)]),
            _AllResult([SimpleNamespace(key="openai", requests=3, cost=Decimal("1.0"), tokens=10, avg_latency_ms=2.0)]),
        ]
    )

    out = await internal_routes.get_llm_throughput(days=0, bucket="bad", provider=None, model=None, call_type=None, status=None, db=fake_db, redis=fake_redis, _="internal")
    assert out["days"] == 1
    assert out["bucket"] == "hour"
    assert out["points"][0]["count"] == 3

    out2 = await internal_routes.get_llm_breakdown(days=0, group_by="provider", limit=999, db=fake_db, redis=fake_redis, _="internal")
    assert out2["days"] == 1
    assert out2["items"][0]["total_cost_usd"] == 1.0
