from __future__ import annotations

import uuid
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes import integrations as integrations_routes
from app.routes import workers as workers_routes


class _ScalarResult:
    def __init__(self, row):
        self._row = row

    def scalar_one_or_none(self):
        return self._row


class _ScalarsResult:
    def __init__(self, rows):
        self._rows = list(rows)

    def scalars(self):
        return SimpleNamespace(all=lambda: list(self._rows))


@pytest.fixture
def workers_client(monkeypatch):
    app = FastAPI()
    app.include_router(workers_routes.router)

    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock()

    async def override_get_db():
        yield db

    app.dependency_overrides[workers_routes.get_db] = override_get_db
    app.dependency_overrides[workers_routes.verify_internal_token] = lambda: None
    return TestClient(app), db


def test_worker_get_tasks_empty(workers_client):
    client, db = workers_client
    db.execute = AsyncMock(return_value=_ScalarsResult([]))
    resp = client.get("/internal/workers/tasks", params={"worker_id": "w"})
    assert resp.status_code == 200
    assert resp.json()["count"] == 0


def test_worker_get_tasks_marks_processing(workers_client):
    client, db = workers_client
    task_id = uuid.uuid4()
    now = datetime.utcnow()
    task = SimpleNamespace(
        id=task_id,
        task_type="embedding",
        priority="low",
        status="pending",
        payload={"x": 1},
        result=None,
        error=None,
        worker_id=None,
        created_at=now,
        updated_at=now,
        started_at=None,
        completed_at=None,
    )
    db.execute = AsyncMock(side_effect=[_ScalarsResult([task]), SimpleNamespace()])
    resp = client.get("/internal/workers/tasks", params={"worker_id": "w", "limit": 1})
    assert resp.status_code == 200
    assert resp.json()["count"] == 1
    assert db.commit.await_count == 1
    assert db.refresh.await_count == 1


def test_worker_submit_result_404_and_400_and_ok(workers_client):
    client, db = workers_client
    task_id = uuid.uuid4()

    # 404
    db.execute = AsyncMock(return_value=_ScalarResult(None))
    resp = client.post(f"/internal/workers/tasks/{task_id}/result", json={"status": "completed", "result": {"ok": True}, "error": None})
    assert resp.status_code == 404

    # 400 invalid status
    now = datetime.utcnow()
    task = SimpleNamespace(
        id=task_id,
        task_type="embedding",
        priority="low",
        status="completed",
        payload={"x": 1},
        result=None,
        error=None,
        worker_id=None,
        created_at=now,
        updated_at=now,
        started_at=None,
        completed_at=None,
    )
    db.execute = AsyncMock(return_value=_ScalarResult(task))
    resp2 = client.post(f"/internal/workers/tasks/{task_id}/result", json={"status": "completed", "result": {}, "error": None})
    assert resp2.status_code == 400

    # ok
    task2 = SimpleNamespace(
        id=task_id,
        task_type="embedding",
        priority="low",
        status="processing",
        payload={"x": 1},
        result=None,
        error=None,
        worker_id="w",
        created_at=now,
        updated_at=now,
        started_at=now,
        completed_at=None,
    )
    db.execute = AsyncMock(return_value=_ScalarResult(task2))
    resp3 = client.post(f"/internal/workers/tasks/{task_id}/result", json={"status": "completed", "result": {"x": 1}, "error": None})
    assert resp3.status_code == 200
    assert db.commit.await_count >= 1


def test_integrations_weeek_routes(monkeypatch):
    app = FastAPI()
    app.include_router(integrations_routes.router)

    class _Weeek:
        async def get_tasks(self, project_id, board_id, tags, tag_names):
            return {"ok": True, "project_id": project_id}

        async def get_workspaces(self):
            return [1]

        async def get_me(self):
            return {"id": 1}

        async def get_boards(self, project_id):
            return [2]

        async def get_projects(self):
            return [3]

        async def get_tags(self):
            return [4]

        async def get_members(self):
            return [5]

    monkeypatch.setattr(integrations_routes, "WeeekClient", _Weeek, raising=True)
    client = TestClient(app)

    resp = client.get("/api/v1/integrations/weeek/tasks", params={"projectId": 1})
    assert resp.status_code == 200
    assert resp.json()["project_id"] == 1

    resp2 = client.get("/api/v1/integrations/weeek/discovery", params={"projectId": 1})
    assert resp2.status_code == 200
    body = resp2.json()
    assert body["workspaces"] == [1]
    assert body["members"] == [5]
