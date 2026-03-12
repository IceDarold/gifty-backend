from __future__ import annotations

import types

import pytest

from app.analytics_events.schema import build_event
from app.analytics_events.topics import subject_for_event
from app.analytics_events import publisher as pub


def test_build_event_defaults():
    ev = build_event(event_type="kpi.quiz_started", source="api")
    assert ev.event_type == "kpi.quiz_started"
    assert ev.version == 1
    assert ev.tenant_id == "default"


def test_subject_for_event():
    assert subject_for_event("kpi.quiz_started") == "analytics.events.v1.kpi"
    assert subject_for_event("llm.call_completed", "x") == "x.llm"


@pytest.mark.asyncio
async def test_publish_disabled(monkeypatch):
    monkeypatch.setattr(pub, "get_settings", lambda: types.SimpleNamespace(
        analytics_events_enabled=False,
        analytics_events_timeout_ms=2000,
        nats_url="nats://localhost:4222",
        analytics_events_subject_prefix="analytics.events.v1",
    ))
    ev = build_event(event_type="kpi.quiz_started", source="api")
    ok = await pub.publish_analytics_event(ev)
    assert ok is False


@pytest.mark.asyncio
async def test_publish_without_nats_dependency(monkeypatch):
    monkeypatch.setattr(pub, "get_settings", lambda: types.SimpleNamespace(
        analytics_events_enabled=True,
        analytics_events_timeout_ms=2000,
        nats_url="nats://localhost:4222",
        analytics_events_subject_prefix="analytics.events.v1",
    ))

    async def fake_connect(self):
        return None

    monkeypatch.setattr(pub.NATSAnalyticsPublisher, "_connect", fake_connect)
    p = pub.NATSAnalyticsPublisher()
    ev = build_event(event_type="kpi.quiz_started", source="api")
    ok = await p.publish(ev)
    assert ok is False
