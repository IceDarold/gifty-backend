from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.utils.errors import AppError, install_exception_handlers


class _Payload(BaseModel):
    x: int


def _make_app():
    app = FastAPI()
    install_exception_handlers(app)

    @app.post("/api/v1/recommendations/generate")
    async def _gen(payload: _Payload):
        # just to trigger RequestValidationError and log body parsing
        return {"ok": True, "x": payload.x}

    @app.get("/raise-app-error")
    async def _raise_app_error():
        raise AppError(code="bad", message="nope", http_status=400, fields={"a": 1})

    @app.get("/raise-http-error")
    async def _raise_http_error():
        raise HTTPException(status_code=400, detail={"reason": "bad"})

    @app.get("/raise-exc")
    async def _raise_exc():
        raise RuntimeError("boom")

    return app


def test_error_response_includes_fields_and_logs_bad_request(monkeypatch, caplog):
    caplog.set_level("WARNING")
    app = _make_app()
    client = TestClient(app)

    resp = client.get("/raise-app-error")
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "bad"
    assert body["error"]["fields"] == {"a": 1}

    # ensure _log_bad_request ran (path matches)
    bad = client.post("/api/v1/recommendations/generate", data="not-json", headers={"content-type": "application/json"})
    assert bad.status_code == 422
    assert any("bad_request path=/api/v1/recommendations/generate" in rec.message for rec in caplog.records)


def test_http_exception_handler_logs_bad_request_dict_detail(caplog):
    caplog.set_level("WARNING")
    client = TestClient(_make_app())

    resp = client.get("/raise-http-error")
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "http_error"
    assert body["error"]["fields"] == {"reason": "bad"}
    assert all("bad_request path=" not in rec.message for rec in caplog.records)


def test_unhandled_exception_handler_posthog_and_notification_failures(monkeypatch, caplog):
    caplog.set_level("ERROR")

    # PostHog configured but capture fails.
    monkeypatch.setattr("app.config.get_settings", lambda: SimpleNamespace(posthog_api_key="k", env="test"))
    def _capture(**_):
        raise RuntimeError("ph down")

    posthog = SimpleNamespace(capture=_capture)
    monkeypatch.setitem(__import__("sys").modules, "posthog", posthog)

    notifier = SimpleNamespace(notify=AsyncMock(side_effect=RuntimeError("notify down")))
    monkeypatch.setattr("app.services.notifications.get_notification_service", lambda: notifier)

    client = TestClient(_make_app(), raise_server_exceptions=False)
    resp = client.get("/raise-exc")
    assert resp.status_code == 500
    body = resp.json()
    assert body["error"]["code"] == "internal_error"

    assert any("Failed to capture error to PostHog" in rec.message for rec in caplog.records)
    assert any("Failed to send system error notification" in rec.message for rec in caplog.records)
