import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from typing import Optional


@pytest.fixture(autouse=True)
def _override_redis_dependency():
    """
    Some endpoints reference app.state.redis in other code paths.
    Keep a lightweight override to avoid AttributeError during app startup.
    """
    from app.redis_client import get_redis
    from fastapi import Request
    from unittest.mock import AsyncMock

    mock_redis = AsyncMock()
    mock_redis.get.return_value = None

    async def _get_redis_override(request: Request):
        return mock_redis

    app.dependency_overrides[get_redis] = _get_redis_override
    app.state.redis = mock_redis
    yield
    app.dependency_overrides.pop(get_redis, None)


@pytest.fixture
def _override_internal_auth_and_db(postgres_session):
    from app.db import get_db
    from fastapi import Header
    from routes.internal import verify_internal_token

    async def _get_db_override():
        yield postgres_session

    async def _verify_override(x_internal_token: Optional[str] = Header(None)):
        return x_internal_token or "test"

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[verify_internal_token] = _verify_override
    yield
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(verify_internal_token, None)


async def _seed_llm_logs(db):
    from app.models import LLMLog, LLMPayload, LLMPromptTemplate
    from sqlalchemy import text

    now = datetime.now(timezone.utc)

    # Ensure isolation across tests (postgres_session uses a persistent DB).
    await db.execute(text("TRUNCATE TABLE llm_logs, llm_payloads, llm_prompt_templates RESTART IDENTITY CASCADE"))
    await db.commit()

    uniq = uuid.uuid4().hex
    system_tpl = LLMPromptTemplate(
        name="system",
        kind="system",
        template_hash=f"h_system_{uniq}",
        content="SYSTEM({language})",
    )
    user_tpl = LLMPromptTemplate(
        name="classify_topic",
        kind="user",
        template_hash=f"h_user_{uniq}",
        content="Topic: {topic}",
    )
    out_payload = LLMPayload(kind="output_text", sha256=f"out_{uniq}", content_text="RAW_OUTPUT")
    raw_payload = LLMPayload(
        kind="raw_response",
        sha256=f"raw_{uniq}",
        content_json={"id": "req_1", "choices": [{"finish_reason": "stop"}]},
    )

    db.add_all([system_tpl, user_tpl, out_payload, raw_payload])
    await db.flush()

    session_a = "sess_a"
    session_b = "sess_b"

    logs = [
        LLMLog(
            id=uuid.uuid4(),
            provider="groq",
            model="m1",
            call_type="classify_topic",
            status="ok",
            created_at=now - timedelta(hours=1),
            latency_ms=1200,
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            cost_usd=0.001,
            session_id=session_a,
            system_prompt_template_id=system_tpl.id,
            system_prompt_params={"language": "ru"},
            user_prompt_template_id=user_tpl.id,
            user_prompt_params={"topic": "cats"},
            output_payload_id=out_payload.id,
            raw_response_payload_id=raw_payload.id,
            finish_reason="stop",
            params={"temperature": 0.1},
        ),
        LLMLog(
            id=uuid.uuid4(),
            provider="groq",
            model="m1",
            call_type="classify_topic",
            status="error",
            error_type="TimeoutError",
            error_message="timeout",
            created_at=now - timedelta(hours=2),
            latency_ms=2500,
            prompt_tokens=20,
            completion_tokens=0,
            total_tokens=20,
            cost_usd=0.002,
            session_id=session_a,
        ),
        LLMLog(
            id=uuid.uuid4(),
            provider="anthropic",
            model="m2",
            call_type="generate_hypotheses",
            status="ok",
            created_at=now - timedelta(days=1, hours=1),
            latency_ms=800,
            prompt_tokens=100,
            completion_tokens=400,
            total_tokens=500,
            cost_usd=0.05,
            session_id=session_b,
        ),
        LLMLog(
            id=uuid.uuid4(),
            provider="anthropic",
            model="m2",
            call_type="generate_hypotheses",
            status="ok",
            created_at=now - timedelta(days=2, hours=3),
            latency_ms=900,
            prompt_tokens=120,
            completion_tokens=380,
            total_tokens=500,
            cost_usd=0.06,
            session_id=session_b,
        ),
        LLMLog(
            id=uuid.uuid4(),
            provider="gemini",
            model="m3",
            call_type="normalize_topics",
            status="ok",
            created_at=now - timedelta(days=3, hours=2),
            latency_ms=300,
            prompt_tokens=5,
            completion_tokens=5,
            total_tokens=10,
            cost_usd=0.0005,
            session_id=None,
        ),
    ]

    db.add_all(logs)
    await db.commit()
    return {
        "system_tpl": system_tpl,
        "user_tpl": user_tpl,
        "out_payload": out_payload,
        "raw_payload": raw_payload,
        "logs": logs,
    }


@pytest.mark.asyncio
async def test_llm_logs_pagination_and_filters(_override_internal_auth_and_db, postgres_session):
    seed = await _seed_llm_logs(postgres_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/internal/analytics/llm/logs", headers={"X-Internal-Token": "x"}, params={"days": 7, "limit": 2, "offset": 0})
        assert res.status_code == 200
        payload = res.json()
        assert payload["limit"] == 2
        assert payload["offset"] == 0
        assert payload["total"] >= 5
        assert len(payload["items"]) == 2

        res2 = await ac.get(
            "/api/v1/internal/analytics/llm/logs",
            headers={"X-Internal-Token": "x"},
            params={"days": 7, "provider": "groq", "status": "ok"},
        )
        assert res2.status_code == 200
        items = res2.json()["items"]
        assert items
        assert all(i["provider"] == "groq" for i in items)
        assert all(i["status"] == "ok" for i in items)

        # model + call_type + session_id filter
        res3 = await ac.get(
            "/api/v1/internal/analytics/llm/logs",
            headers={"X-Internal-Token": "x"},
            params={"days": 7, "model": "m1", "call_type": "classify_topic", "session_id": "sess_a"},
        )
        assert res3.status_code == 200
        items3 = res3.json()["items"]
        assert len(items3) == 2

    # ensure we created one details-ready log
    assert seed["logs"][0].system_prompt_template_id is not None


@pytest.mark.asyncio
async def test_llm_log_details_full(_override_internal_auth_and_db, postgres_session):
    seed = await _seed_llm_logs(postgres_session)
    target = seed["logs"][0]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        bad = await ac.get("/api/v1/internal/analytics/llm/logs/not-a-uuid", headers={"X-Internal-Token": "x"})
        assert bad.status_code == 400

        res = await ac.get(f"/api/v1/internal/analytics/llm/logs/{target.id}", headers={"X-Internal-Token": "x"})
        assert res.status_code == 200
        body = res.json()
        assert body["id"] == str(target.id)
        assert body["system_prompt"]["name"] == "system"
        assert body["system_prompt"]["rendered"] == "SYSTEM(ru)"
        assert body["user_prompt"]["name"] == "classify_topic"
        assert body["user_prompt"]["rendered"] == "Topic: cats"
        assert body["response"]["output_text"] == "RAW_OUTPUT"
        assert body["response"]["raw_response"]["id"] == "req_1"
        assert isinstance(body.get("related_calls"), list)
        assert any(c["id"] == str(target.id) for c in body["related_calls"])


@pytest.mark.asyncio
async def test_llm_throughput(_override_internal_auth_and_db, postgres_session):
    await _seed_llm_logs(postgres_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get(
            "/api/v1/internal/analytics/llm/throughput",
            headers={"X-Internal-Token": "x"},
            params={"days": 7, "bucket": "day"},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["bucket"] == "day"
        assert len(body["points"]) >= 3

        res2 = await ac.get(
            "/api/v1/internal/analytics/llm/throughput",
            headers={"X-Internal-Token": "x"},
            params={"days": 7, "bucket": "day", "provider": "groq"},
        )
        assert res2.status_code == 200
        body2 = res2.json()
        assert sum(p["count"] for p in body2["points"]) == 2


@pytest.mark.asyncio
async def test_llm_breakdown_with_filters(_override_internal_auth_and_db, postgres_session):
    await _seed_llm_logs(postgres_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get(
            "/api/v1/internal/analytics/llm/breakdown",
            headers={"X-Internal-Token": "x"},
            params={"days": 7, "group_by": "provider", "status": "ok"},
        )
        assert res.status_code == 200
        body = res.json()
        keys = {i["key"] for i in body["items"]}
        assert "groq" in keys
        assert "anthropic" in keys
        assert "gemini" in keys

        res2 = await ac.get(
            "/api/v1/internal/analytics/llm/breakdown",
            headers={"X-Internal-Token": "x"},
            params={"days": 7, "group_by": "call_type", "provider": "groq"},
        )
        assert res2.status_code == 200
        items = res2.json()["items"]
        assert len(items) == 1
        assert items[0]["key"] == "classify_topic"
        assert items[0]["requests"] == 2


@pytest.mark.asyncio
async def test_llm_stats(_override_internal_auth_and_db, postgres_session):
    await _seed_llm_logs(postgres_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/internal/analytics/llm/stats", headers={"X-Internal-Token": "x"}, params={"days": 7})
        assert res.status_code == 200
        body = res.json()
        assert body["total"] >= 5
        assert 0.0 <= body["error_rate"] <= 1.0
        assert body["p95_latency_ms"] >= body["p50_latency_ms"]
        assert body["total_cost_usd"] > 0

        res2 = await ac.get(
            "/api/v1/internal/analytics/llm/stats",
            headers={"X-Internal-Token": "x"},
            params={"days": 7, "provider": "groq"},
        )
        assert res2.status_code == 200
        body2 = res2.json()
        assert body2["total"] == 2
        assert body2["errors"] == 1


@pytest.mark.asyncio
async def test_llm_outliers(_override_internal_auth_and_db, postgres_session):
    await _seed_llm_logs(postgres_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get(
            "/api/v1/internal/analytics/llm/outliers",
            headers={"X-Internal-Token": "x"},
            params={"days": 7, "metric": "latency", "limit": 5},
        )
        assert res.status_code == 200
        items = res.json()["items"]
        assert items
        latencies = [int(i["latency_ms"] or 0) for i in items]
        assert latencies == sorted(latencies, reverse=True)

        res2 = await ac.get(
            "/api/v1/internal/analytics/llm/outliers",
            headers={"X-Internal-Token": "x"},
            params={"days": 7, "metric": "tokens", "limit": 5},
        )
        assert res2.status_code == 200
        items2 = res2.json()["items"]
        tokens = [int(i["total_tokens"] or 0) for i in items2]
        assert tokens == sorted(tokens, reverse=True)

        res3 = await ac.get(
            "/api/v1/internal/analytics/llm/outliers",
            headers={"X-Internal-Token": "x"},
            params={"days": 7, "metric": "cost", "limit": 5},
        )
        assert res3.status_code == 200
        items3 = res3.json()["items"]
        costs = [float(i["cost_usd"] or 0) for i in items3]
        assert costs == sorted(costs, reverse=True)
