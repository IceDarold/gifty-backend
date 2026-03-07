from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.notifications import NotificationService


@pytest.mark.anyio
async def test_notification_service_serializes_datetime_and_pydantic_like(monkeypatch):
    monkeypatch.setattr("app.services.notifications.get_settings", lambda: SimpleNamespace(rabbitmq_url="amqp://guest:guest@localhost/"))

    published = {}

    class _Channel:
        def queue_declare(self, queue: str, durable: bool = True):
            return None

        def basic_publish(self, *, exchange: str, routing_key: str, body: str, properties=None):
            published["exchange"] = exchange
            published["routing_key"] = routing_key
            published["body"] = body

    class _Conn:
        def channel(self):
            return _Channel()

        def close(self):
            return None

    svc = NotificationService()
    monkeypatch.setattr(svc, "_get_connection", lambda: _Conn())

    class _Pyd1:
        def dict(self):
            return {"x": 1}

    class _Pyd2:
        def model_dump(self):
            return {"y": 2}

    ok = await svc.notify(
        topic="t",
        message="m",
        data={"when": datetime(2025, 1, 1, tzinfo=timezone.utc), "p1": _Pyd1(), "p2": _Pyd2()},
    )
    assert ok is True
    assert published["routing_key"] == "notifications"
    assert '"topic": "t"' in published["body"]
    assert "2025-01-01T00:00:00" in published["body"]


@pytest.mark.anyio
async def test_notification_service_returns_false_on_publish_error(monkeypatch):
    monkeypatch.setattr("app.services.notifications.get_settings", lambda: SimpleNamespace(rabbitmq_url="amqp://guest:guest@localhost/"))

    svc = NotificationService()
    monkeypatch.setattr(svc, "_get_connection", lambda: (_ for _ in ()).throw(RuntimeError("no conn")))

    ok = await svc.notify(topic="t", message="m", data={"x": 1})
    assert ok is False

