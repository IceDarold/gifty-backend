from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from routes import internal as internal_routes


class _FakeHttpxResp:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _FakeHttpxClient:
    def __init__(self, post_resp: _FakeHttpxResp | None = None, get_resp: _FakeHttpxResp | None = None, exc: Exception | None = None):
        self._post_resp = post_resp
        self._get_resp = get_resp
        self._exc = exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json=None):
        if self._exc:
            raise self._exc
        return self._post_resp

    async def get(self, url):
        if self._exc:
            raise self._exc
        return self._get_resp


def test_queue_tasks_error_and_success(client, monkeypatch):
    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", lambda timeout=8.0: _FakeHttpxClient(post_resp=_FakeHttpxResp(500, {})))
    resp = client.get("/api/v1/internal/queues/tasks")
    assert resp.status_code == 200
    assert resp.json()["status"] == "error"

    payload = [
        {"payload": {"site_key": "s", "source_id": 1, "run_id": 2, "type": "list", "url": "u", "config": {"discovery_name": "c"}}},
        {"payload": "not-a-dict"},
    ]
    monkeypatch.setattr(httpx, "AsyncClient", lambda timeout=8.0: _FakeHttpxClient(post_resp=_FakeHttpxResp(200, payload)))
    ok = client.get("/api/v1/internal/queues/tasks", params={"limit": 2})
    assert ok.status_code == 200
    body = ok.json()
    assert body["status"] == "ok"
    assert body["count"] == 2
    assert body["items"][0]["task"]["site_key"] == "s"


def test_queue_tasks_exception_is_caught(client, monkeypatch):
    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", lambda timeout=8.0: _FakeHttpxClient(exc=RuntimeError("boom")))
    resp = client.get("/api/v1/internal/queues/tasks")
    assert resp.status_code == 200
    assert resp.json()["status"] == "error"


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


class _AllResult:
    def __init__(self, rows):
        self._rows = list(rows)

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None


def test_queue_history_validates_status(client):
    resp = client.get("/api/v1/internal/queues/history", params={"status": "wat"})
    assert resp.status_code == 400


def test_queue_history_and_details(fake_db, client):
    run = SimpleNamespace(
        id=1,
        source_id=10,
        status="completed",
        items_scraped=1,
        items_new=1,
        error_message=None,
        duration_seconds=None,
        created_at=datetime(2025, 1, 1),  # naive
        updated_at=datetime(2025, 1, 1, 0, 0, 10),  # naive
        logs="Batch ingested: 1 products, 2 categories",
    )
    source = SimpleNamespace(
        id=10,
        site_key="site",
        type="list",
        strategy="s",
        url="u",
        config={"discovery_name": "D"},
    )
    category = SimpleNamespace(name="Cat")

    fake_db.execute = AsyncMock(
        side_effect=[
            _ScalarResult(1),  # total
            _AllResult([(run, source, category)]),  # items
            _AllResult([]),  # details not found
            _AllResult([(run, source, category)]),  # details found
        ]
    )

    resp = client.get("/api/v1/internal/queues/history", params={"limit": 10})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "ok"
    assert body["items"][0]["categories_scraped"] == 2
    assert body["items"][0]["duration_seconds"] == 10.0

    not_found = client.get("/api/v1/internal/queues/history/999")
    assert not_found.status_code == 404

    ok = client.get("/api/v1/internal/queues/history/1")
    assert ok.status_code == 200
    assert ok.json()["item"]["category_name"] == "Cat"


def test_queue_stats_uses_fetcher(client, monkeypatch):
    monkeypatch.setattr(internal_routes, "_fetch_rabbit_queue_stats", AsyncMock(return_value={"status": "ok", "messages_total": 1}), raising=True)
    resp = client.get("/api/v1/internal/queues/stats")
    assert resp.status_code == 200
    assert resp.json()["messages_total"] == 1
