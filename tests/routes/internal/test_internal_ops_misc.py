from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from routes import internal as internal_routes


class _ScalarOneOrNone:
    def __init__(self, row):
        self._row = row

    def scalar_one_or_none(self):
        return self._row


class _Rowcount:
    def __init__(self, rowcount: int):
        self.rowcount = rowcount


def test_scoring_endpoints_return_410(client):
    resp = client.get("/api/v1/internal/scoring/tasks")
    assert resp.status_code == 410
    resp2 = client.post("/api/v1/internal/scoring/submit")
    assert resp2.status_code == 410


@pytest.mark.asyncio
async def test_bulk_update_ops_sources(monkeypatch):
    db = AsyncMock()
    db.commit = AsyncMock()
    db.execute = AsyncMock(return_value=_Rowcount(3))

    out = await internal_routes.bulk_update_ops_sources(payload={"source_ids": [1, 2, 3], "priority": 10, "is_active": True}, db=db)
    assert out["updated"] == 3

    out2 = await internal_routes.bulk_update_ops_sources(payload={"source_ids": []}, db=db)
    assert out2["updated"] == 0


@pytest.mark.asyncio
async def test_run_discovery_for_site_creates_source_and_publishes(monkeypatch, fake_redis):
    now = datetime.now(timezone.utc)
    hub = SimpleNamespace(site_key="site", url="u", strategy="discovery", is_active=True, status="waiting", config={}, next_sync_at=None)

    db = AsyncMock()
    db.commit = AsyncMock()
    async def _refresh(obj):
        if getattr(obj, "id", None) is None:
            obj.id = 1
        return None

    db.refresh = AsyncMock(side_effect=_refresh)
    db.add = lambda obj: None

    # hub exists, source missing
    db.execute = AsyncMock(side_effect=[_ScalarOneOrNone(hub), _ScalarOneOrNone(None)])

    monkeypatch.setattr(internal_routes, "_fetch_rabbit_queue_stats", AsyncMock(return_value={"status": "ok", "messages_total": 1}), raising=True)
    monkeypatch.setattr("app.utils.rabbitmq.publish_parsing_task", lambda task: True, raising=False)

    class _Repo:
        def __init__(self, db):
            pass

        async def set_queued(self, source_id: int):
            return None

    monkeypatch.setattr(internal_routes, "ParsingRepository", _Repo, raising=True)

    out = await internal_routes.run_discovery_for_site(site_key="site", db=db, redis=fake_redis)
    assert out["status"] == "ok"
    assert hub.status == "queued"


@pytest.mark.asyncio
async def test_stream_ops_events_emits_queue_snapshot_and_event(monkeypatch, fake_db, fake_redis):
    monkeypatch.setattr(internal_routes, "verify_internal_token", AsyncMock(return_value="internal"), raising=True)
    monkeypatch.setattr(internal_routes, "_fetch_rabbit_queue_stats", AsyncMock(return_value={"status": "ok", "messages_total": 1}), raising=True)

    # Publish one event before starting the generator.
    await fake_redis.publish(
        internal_routes.OPS_EVENTS_CHANNEL,
        json.dumps({"type": "worker.pause_changed", "payload": {"worker_id": "w", "paused": True}}),
    )

    resp = await internal_routes.stream_ops_events(db=fake_db, redis=fake_redis, x_internal_token="t")
    chunks = []
    async for chunk in resp.body_iterator:
        chunks.append(chunk)
        if len(chunks) >= 2:
            break
    await resp.body_iterator.aclose()

    text = "".join(chunks)
    assert "event: queue.updated" in text
    assert "event: worker.pause_changed" in text
