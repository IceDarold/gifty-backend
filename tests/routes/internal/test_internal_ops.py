from __future__ import annotations

from tests.routes.internal.conftest import assert_ok


def test_ops_runtime_settings_get(client):
    resp = client.get("/api/v1/internal/ops/runtime-settings")
    assert_ok(resp)


def test_ops_runtime_settings_put_and_throttle(client):
    resp1 = client.put("/api/v1/internal/ops/runtime-settings", json={"ops_aggregator_enabled": False})
    body1 = assert_ok(resp1)
    assert body1["item"]["ops_aggregator_enabled"] is False

    # Second immediate update should be rate-limited (FakeRedis nx/px emulates this).
    resp2 = client.put("/api/v1/internal/ops/runtime-settings", json={"ops_aggregator_enabled": True})
    assert resp2.status_code == 429


def test_ops_runtime_settings_put_validates_intervals(client):
    resp = client.put("/api/v1/internal/ops/runtime-settings", json={"ops_client_intervals": {"unknown.key": 1}})
    assert resp.status_code == 400


def test_ops_scheduler_pause_resume(client, fake_redis):
    pause = client.post("/api/v1/internal/ops/scheduler/pause")
    body = assert_ok(pause)
    assert body["paused"] is True
    assert fake_redis._kv.get("ops:scheduler:paused") is not None

    resume = client.post("/api/v1/internal/ops/scheduler/resume")
    body2 = assert_ok(resume)
    assert body2["paused"] is False
    assert "ops:scheduler:paused" not in fake_redis._kv


def test_ops_worker_pause_resume(client, fake_redis):
    resp = client.post("/api/v1/internal/ops/workers/w1/pause")
    body = assert_ok(resp)
    assert body["worker_id"] == "w1"
    assert fake_redis._kv.get("worker_pause:w1") is not None

    resp2 = client.post("/api/v1/internal/ops/workers/w1/resume")
    body2 = assert_ok(resp2)
    assert body2["worker_id"] == "w1"
    assert "worker_pause:w1" not in fake_redis._kv
