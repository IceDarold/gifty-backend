from __future__ import annotations

import pytest

from app.auth import dependencies


@pytest.mark.asyncio
async def test_verify_internal_token_ok(monkeypatch):
    settings = type("S", (), {"internal_api_token": "t"})()
    out = await dependencies.verify_internal_token(x_internal_token="t", settings=settings)
    assert out == "t"


@pytest.mark.asyncio
async def test_verify_internal_token_reject(monkeypatch):
    settings = type("S", (), {"internal_api_token": "t"})()
    with pytest.raises(Exception) as exc:
        await dependencies.verify_internal_token(x_internal_token="nope", settings=settings)
    assert getattr(exc.value, "status_code", None) == 403
