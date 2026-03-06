from __future__ import annotations

import time
from unittest.mock import AsyncMock

import pytest

from app.services.llm import cost_estimator


@pytest.mark.asyncio
async def test_price_registry_uses_fallback_and_default():
    prices = await cost_estimator._registry.get_prices_for_model("gpt-4o")
    assert "input" in prices and "output" in prices

    prices2 = await cost_estimator._registry.get_prices_for_model("unknown-model")
    assert prices2 == {"input": 0.5, "output": 1.5}


@pytest.mark.asyncio
async def test_price_registry_fetch_remote_prices_happy(monkeypatch):
    registry = cost_estimator.PriceRegistry()
    registry._prices = {}
    registry._last_updated = 0

    class _Resp:
        status_code = 200

        def json(self):
            return {
                "data": [
                    {"id": "m1", "pricing": {"prompt": "0.000001", "completion": "0.000002"}},
                ]
            }

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url):
            return _Resp()

    monkeypatch.setattr(cost_estimator.httpx, "AsyncClient", lambda timeout=10.0: _Client())

    registry._update_interval = 0
    prices = await registry.get_prices_for_model("m1")
    assert prices["input"] == 1.0
    assert prices["output"] == 2.0


@pytest.mark.asyncio
async def test_estimate_cost_rounding(monkeypatch):
    monkeypatch.setattr(cost_estimator._registry, "get_prices_for_model", AsyncMock(return_value={"input": 1.0, "output": 3.0}))
    out = await cost_estimator.estimate_cost("x", prompt_tokens=1_000_000, completion_tokens=1_000_000)
    assert out == 4.0

