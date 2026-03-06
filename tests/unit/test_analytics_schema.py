from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.analytics import schema as analytics_schema


@dataclass
class _FakeSettings:
    posthog_api_key: str | None = "ph_key"
    posthog_project_id: str | None = "123"
    prometheus_url: str = "http://prom"
    loki_url: str = "http://loki"


class _FakeRedis:
    def __init__(self):
        self._kv: dict[str, str] = {}

    async def get(self, key: str):
        return self._kv.get(key)

    async def setex(self, key: str, ttl: int, value: str):
        self._kv[key] = value
        return True


class _FakeScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value

    def scalar_one(self):
        return self._value


class _FakeOneResult:
    def __init__(self, row):
        self._row = row

    def one(self):
        return self._row

    def one_or_none(self):
        return self._row


class _FakeAllResult:
    def __init__(self, rows):
        self._rows = list(rows)

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None

    def scalars(self):
        return SimpleNamespace(all=lambda: list(self._rows))

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None

    def scalar_one(self):
        return self._rows[0] if self._rows else None

    def scalar(self):
        return self._rows[0] if self._rows else None


@pytest.mark.asyncio
async def test_query_posthog_returns_empty_when_unconfigured():
    redis = _FakeRedis()
    settings = _FakeSettings(posthog_api_key=None, posthog_project_id=None)
    out = await analytics_schema.query_posthog({"kind": "X"}, settings, redis, "k")
    assert out == {}


@pytest.mark.asyncio
async def test_query_posthog_uses_cache():
    redis = _FakeRedis()
    settings = _FakeSettings()
    redis._kv["k"] = json.dumps({"results": [1]})
    out = await analytics_schema.query_posthog({"kind": "X"}, settings, redis, "k")
    assert out == {"results": [1]}


@pytest.mark.asyncio
async def test_query_posthog_success_sets_cache(monkeypatch):
    redis = _FakeRedis()
    settings = _FakeSettings()

    class _Resp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"results": [{"data": [1]}]}

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None):
            return _Resp()

    monkeypatch.setattr(analytics_schema.httpx, "AsyncClient", lambda timeout=30.0: _Client())
    out = await analytics_schema.query_posthog({"kind": "X"}, settings, redis, "k", cache_ttl=1)
    assert out.get("results")
    assert json.loads(redis._kv["k"])["results"][0]["data"] == [1]


@pytest.mark.asyncio
async def test_query_posthog_errors_are_swallowed(monkeypatch):
    redis = _FakeRedis()
    settings = _FakeSettings()

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr(analytics_schema.httpx, "AsyncClient", lambda timeout=30.0: _Client())
    out = await analytics_schema.query_posthog({"kind": "X"}, settings, redis, "k")
    assert out == {}


@pytest.mark.asyncio
async def test_query_fields_stats_trends_funnel(monkeypatch):
    settings = _FakeSettings()
    redis = _FakeRedis()

    async def _fake_posthog(query, settings, redis, cache_key, cache_ttl=300):
        kind = query.get("kind")
        if kind == "TrendsQuery" and query.get("series", [{}])[0].get("math") == "dau" and query.get("interval") == "day":
            return {"results": [{"labels": ["d1", "d2"], "data": [1, 2]}]}
        if kind == "TrendsQuery" and query.get("series", [{}])[0].get("math") == "dau":
            return {"results": [{"data": [0, 3]}]}
        if kind == "FunnelsQuery" and query.get("series", [{}])[0].get("event") == "quiz_started":
            if len(query.get("series") or []) > 2:
                return {"results": [{"name": "A", "count": 1, "conversionRates": {"total": 0.5}}]}
            return {"results": [[{"count": 10}, {"count": 7}]]}
        if kind == "FunnelsQuery" and query.get("series", [{}])[0].get("event") == "results_shown":
            return {"results": [[{"count": 20}, {"count": 4}]]}
        if kind == "TrendsQuery" and query.get("series", [{}])[0].get("event") == "quiz_started":
            return {"results": [{"data": [5, 6]}]}
        if kind == "FunnelsQuery":
            return {"results": [{"name": "A", "count": 1, "conversionRates": {"total": 0.5}}]}
        return {}

    monkeypatch.setattr(analytics_schema, "query_posthog", _fake_posthog)
    q = analytics_schema.Query()
    info = SimpleNamespace(context={"settings": settings, "redis": redis})

    stats = await q.stats(info)
    assert stats.dau == 3
    assert stats.quiz_completion_rate == 70.0
    assert stats.gift_ctr == 20.0

    trends = await q.trends(info, days=999)
    assert trends.dates == ["d1", "d2"]
    assert trends.dau_trend == [1, 2]
    assert trends.quiz_starts == [5, 6]

    steps = await q.funnel(info)
    assert steps and steps[0].conversion_rate == 50.0


@pytest.mark.asyncio
async def test_query_fields_technical_cache_and_fetch(monkeypatch):
    settings = _FakeSettings()
    redis = _FakeRedis()
    q = analytics_schema.Query()

    # Cached path
    redis._kv["analytics:technical_stats"] = json.dumps(
        {
            "api_health": "healthy",
            "requests_per_minute": 1.0,
            "error_rate_5xx": 0.0,
            "last_errors": [],
            "last_updated": "x",
        }
    )
    info = SimpleNamespace(context={"settings": settings, "redis": redis})
    cached = await q.technical(info)
    assert cached.api_health == "healthy"

    # Fetch path
    redis._kv.pop("analytics:technical_stats", None)

    class _Resp:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, params=None):
            qv = (params or {}).get("query")
            if qv and "http_request_duration_seconds_count" in qv and "5.." not in qv:
                return _Resp(200, {"data": {"result": [{"value": [0, "2.5"]}]}})
            if qv and "status=~\"5..\"" in qv:
                return _Resp(200, {"data": {"result": [{"value": [0, "0.01"]}]}})
            # Loki
            return _Resp(200, {"data": {"result": [{"values": [["1", "err"]]}]}})

    monkeypatch.setattr(analytics_schema.httpx, "AsyncClient", lambda timeout=5.0: _Client())
    fetched = await q.technical(SimpleNamespace(context={"settings": settings, "redis": redis}))
    assert fetched.requests_per_minute == 2.5
    assert fetched.error_rate_5xx == 0.01
    assert fetched.last_errors == ["err"]


@pytest.mark.asyncio
async def test_query_fields_scraping_and_catalog_and_health_and_hypothesis(monkeypatch):
    settings = _FakeSettings()
    redis = _FakeRedis()
    db = AsyncMock()
    q = analytics_schema.Query()

    # scraping(): first two execute() calls are scalar queries
    db.execute = AsyncMock(
        side_effect=[
            _FakeScalarResult(2),  # sources_count
            _FakeScalarResult(3),  # unmapped_count
            _FakeOneResult(SimpleNamespace(total=10, hits=7, avg_results=2.0)),  # catalog_coverage metrics
            _FakeAllResult([SimpleNamespace(search_query="x", count=4)]),  # gaps rows
            _FakeScalarResult(80.0),  # system_health hit_rate
            _FakeScalarResult(25.0),  # system_health like_rate
            _FakeScalarResult(123.0),  # system_health avg perf
        ]
    )

    class _Resp:
        def __init__(self, payload):
            self.status_code = 200
            self._payload = payload

        def json(self):
            return self._payload

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, params=None):
            qv = (params or {}).get("query")
            if qv == "sum(scraped_items_total)":
                return _Resp({"data": {"result": [{"value": [0, "10"]}]}})
            if qv and "ingestion_batches_total" in qv:
                return _Resp({"data": {"result": [{"value": [0, "2"]}]}})
            if qv and "sum by (spider)" in qv:
                return _Resp({"data": {"result": [{"metric": {"spider": "s"}, "value": [0, "3"]}]}})
            return _Resp({"data": {"result": []}})

    monkeypatch.setattr(analytics_schema.httpx, "AsyncClient", lambda timeout=30.0: _Client())

    info = SimpleNamespace(context={"db": db, "settings": settings, "redis": redis})
    scraping = await q.scraping(info)
    assert scraping.active_sources == 2
    assert scraping.unmapped_categories == 3
    assert scraping.total_scraped_items == 10
    assert scraping.ingestion_errors == 2
    assert scraping.spiders["s"]["items_scraped"] == 3

    catalog = await q.catalog_coverage(info, days=7)
    assert catalog.total_searches == 10
    assert catalog.hit_rate == 70.0
    assert catalog.top_catalog_gaps[0].misses == 4

    health = await q.system_health(info)
    assert health.status == "healthy"

    # hypothesis_details(): missing and found
    hyp_id = uuid.uuid4()
    db2 = AsyncMock()
    db2.execute = AsyncMock(
        side_effect=[
            _FakeAllResult([]),  # hypothesis row none
            _FakeAllResult([SimpleNamespace(id=hyp_id, title="t", track_title="tr", user_reaction="like", created_at=datetime(2025, 1, 1))]),
            _FakeAllResult([SimpleNamespace(gift_id="g", rank_position=1, similarity_score=0.1, was_clicked=True)]),
            _FakeAllResult([SimpleNamespace(search_query="q", results_count=2)]),
        ]
    )
    info2 = SimpleNamespace(context={"db": db2})
    none = await q.hypothesis_details(info2, id=hyp_id)
    assert none is None
    found = await q.hypothesis_details(info2, id=hyp_id)
    assert found.total_results_found == 2
    assert found.products[0]["gift_id"] == "g"


@pytest.mark.asyncio
async def test_query_fields_ai_usage_llm_logs_experiment_and_demand(monkeypatch):
    q = analytics_schema.Query()
    db = AsyncMock()

    now = datetime(2025, 1, 1, tzinfo=timezone.utc)
    llm_row = SimpleNamespace(
        id=uuid.uuid4(),
        provider="p",
        model="m",
        call_type="t",
        latency_ms=123,
        total_tokens=7,
        cost_usd=0.01,
        created_at=now,
        variant_id="v1",
        experiment_id="e1",
        session_id="s1",
    )

    db.execute = AsyncMock(
        side_effect=[
            _FakeOneResult(SimpleNamespace(tokens=10, cost=1.0, latency=50.0, count=2)),  # ai_usage totals
            _FakeAllResult([("p", 2)]),  # ai_usage distribution
            _FakeAllResult([llm_row]),  # llm_logs list
            _FakeAllResult([SimpleNamespace(variant_id="v1", count=3, latency=10.0, cost=0.5, tokens=100)]),  # experiment_report variant stats
            _FakeScalarResult(2),  # likes count
            _FakeScalarResult(4),  # gen_calls count
            _FakeAllResult([SimpleNamespace(predicted_category="cat", count=5, avg_results=1.0, zero_results=1)]),  # demand rows
        ]
    )

    # Provide experiment config names (schema imports this inside the resolver).
    import app.core.logic_config as logic_config_mod

    monkeypatch.setattr(
        logic_config_mod,
        "logic_config",
        SimpleNamespace(experiments=[{"id": "e1", "variants": {"v1": {"name": "V"}}}]),
        raising=True,
    )

    info = SimpleNamespace(context={"db": db})
    usage = await q.ai_usage(info, days=7)
    assert usage.total_tokens == 10
    assert usage.provider_distribution["p"] == 2

    logs = await q.llm_logs(info, limit=10)
    assert logs and logs[0].provider == "p"

    rep = await q.experiment_report(info, experiment_id="e1")
    assert rep and rep.variants[0].conversion_rate == 50.0

    forecast = await q.demand_forecast(info, days=7)
    assert forecast.total_searches_analyzed == 5
