from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any
import os
import sqlite3
import sys
import types

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from integrations.takprodam.models import GiftCandidate
from recommendations.ranker_v1 import RankingResult

os.environ.setdefault("API_BASE", "http://testserver")
os.environ.setdefault("FRONTEND_BASE", "http://testserver")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("GOOGLE_CLIENT_ID", "dummy")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "dummy")
os.environ.setdefault("YANDEX_CLIENT_ID", "dummy")
os.environ.setdefault("YANDEX_CLIENT_SECRET", "dummy")
os.environ.setdefault("VK_CLIENT_ID", "dummy")
os.environ.setdefault("VK_CLIENT_SECRET", "dummy")

fake_aiosqlite = types.SimpleNamespace(
    paramstyle=sqlite3.paramstyle,
    DatabaseError=sqlite3.DatabaseError,
    IntegrityError=sqlite3.IntegrityError,
    Warning=sqlite3.Warning,
    InterfaceError=sqlite3.InterfaceError,
    OperationalError=sqlite3.OperationalError,
    ProgrammingError=sqlite3.ProgrammingError,
    Error=sqlite3.Error,
    NotSupportedError=sqlite3.NotSupportedError,
    version=sqlite3.version,
    sqlite_version=sqlite3.sqlite_version,
    sqlite_version_info=sqlite3.sqlite_version_info,
    threadsafety=sqlite3.threadsafety,
    complete_statement=sqlite3.complete_statement,
    register_adapter=sqlite3.register_adapter,
    register_converter=sqlite3.register_converter,
    version_info=sqlite3.version_info,
)


async def _fake_connect(*args, **kwargs):
    return sqlite3.connect(":memory:")


fake_aiosqlite.connect = _fake_connect
sys.modules.setdefault("aiosqlite", fake_aiosqlite)

from routes import recommendations as rec_module


@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(rec_module.router)
    from app.utils.errors import install_exception_handlers

    install_exception_handlers(app)

    async def override_get_db():
        yield SimpleNamespace()

    async def override_get_redis():
        return SimpleNamespace()

    app.dependency_overrides[rec_module.get_db] = override_get_db
    app.dependency_overrides[rec_module.get_redis] = override_get_redis
    app.dependency_overrides[rec_module.get_optional_user] = lambda: None

    return TestClient(app)


@pytest.fixture
def pipeline_mocks(monkeypatch):
    events: list[tuple[str, dict[str, Any]]] = []
    created: dict[str, Any] = {}

    sample_candidates = [
        GiftCandidate(
            gift_id=f"gift-{i}",
            title=f"Gift {i}",
            description="Nice gift",
            product_url=f"https://example.com/{i}",
            price=10 + i,
            raw={},
        )
        for i in range(12)
    ]

    queries = [
        {"query": "cozy blanket", "bucket": "vibe", "reason": "cozy"},
        {"query": "scented candle", "bucket": "vibe", "reason": "cozy"},
    ]

    def fake_generate_queries(quiz, ruleset):
        return queries

    def fake_collect_candidates(*_, **__):
        return sample_candidates, {"collector": True}

    def fake_rank_candidates(quiz, candidates, debug=False):
        return RankingResult(
            featured_gift_id=candidates[0].gift_id,
            gift_ids=[c.gift_id for c in candidates[:10]],
            debug={"ranker": debug},
        )

    async def fake_create_quiz_run(db, *, user_id, anon_id, answers_json):
        created["quiz_run"] = SimpleNamespace(id=uuid.uuid4(), user_id=user_id, anon_id=anon_id)
        return created["quiz_run"]

    async def fake_create_recommendation_run(
        db, *, quiz_run_id, engine_version, featured_gift_id, gift_ids, debug_json=None
    ):
        created["recommendation_run"] = SimpleNamespace(
            id=uuid.uuid4(),
            quiz_run_id=quiz_run_id,
            engine_version=engine_version,
            featured_gift_id=featured_gift_id,
            gift_ids=gift_ids,
            debug_json=debug_json,
        )
        return created["recommendation_run"]

    async def fake_log_event(db, event_name, **kwargs):
        events.append((event_name, kwargs))

    monkeypatch.setattr(rec_module, "generate_queries", fake_generate_queries)
    monkeypatch.setattr(rec_module, "collect_candidates", fake_collect_candidates)
    monkeypatch.setattr(rec_module, "rank_candidates", fake_rank_candidates)
    monkeypatch.setattr(rec_module, "create_quiz_run", fake_create_quiz_run)
    monkeypatch.setattr(rec_module, "create_recommendation_run", fake_create_recommendation_run)
    monkeypatch.setattr(rec_module, "log_event", fake_log_event)

    return {"events": events, "created": created, "queries": queries, "candidates": sample_candidates}


def _payload(debug: bool = False) -> dict[str, Any]:
    return {
        "recipient_age": 25,
        "relationship": "friend",
        "occasion": "birthday",
        "vibe": "cozy",
        "interests": ["music"],
        "interests_description": "loves soft things",
        "budget": 100,
        "city": "Moscow",
        "debug": debug,
    }


def test_generate_happy_path(client, pipeline_mocks):
    response = client.post("/api/v1/recommendations/generate", json=_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["featured_gift_id"] == "gift-0"
    assert len(body["gift_ids"]) == 10
    assert body["gift_ids"][0] == "gift-0"
    assert body["debug"] is None
    assert len(pipeline_mocks["events"]) == 2


def test_generate_debug_mode(client, pipeline_mocks):
    response = client.post("/api/v1/recommendations/generate", json=_payload(debug=True))
    assert response.status_code == 200
    body = response.json()
    assert body["debug"]
    assert body["debug"]["queries"] == pipeline_mocks["queries"]
    assert body["debug"]["candidate_collector"] == {"collector": True}
    assert body["debug"]["ranker"] == {"ranker": True}


def test_generate_no_candidates(client, monkeypatch, pipeline_mocks):
    def fake_collect(*_, **__):
        return [], {}

    monkeypatch.setattr(rec_module, "collect_candidates", fake_collect)
    response = client.post("/api/v1/recommendations/generate", json=_payload())
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "no_candidates_found"


def test_generate_guest_anon_id(client, pipeline_mocks):
    response = client.post(
        "/api/v1/recommendations/generate",
        json=_payload(),
        headers={"X-Anon-Id": "guest-123"},
    )
    assert response.status_code == 200
    assert pipeline_mocks["created"]["quiz_run"].anon_id == "guest-123"


def test_generate_with_logged_in_user(client, pipeline_mocks, monkeypatch):
    class DummyUser:
        def __init__(self) -> None:
            self.id = uuid.uuid4()

    async def override_optional_user():
        return DummyUser()

    client.app.dependency_overrides[rec_module.get_optional_user] = override_optional_user

    response = client.post("/api/v1/recommendations/generate", json=_payload())
    assert response.status_code == 200
    assert pipeline_mocks["created"]["quiz_run"].user_id is not None
