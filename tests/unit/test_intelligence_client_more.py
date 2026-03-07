from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from app.services import intelligence as mod


class _AsyncClientStub:
    def __init__(self, response: httpx.Response | Exception):
        self._item = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *_args, **_kwargs):
        if isinstance(self._item, Exception):
            raise self._item
        return self._item


@pytest.mark.anyio
async def test_get_embeddings_low_priority_requires_db():
    client = mod.IntelligenceAPIClient()
    with pytest.raises(ValueError, match="Database session required"):
        await client.get_embeddings(["x"], priority="low", db=None)


@pytest.mark.anyio
async def test_get_embeddings_runpod_falls_back_when_call_fails(monkeypatch):
    client = mod.IntelligenceAPIClient()
    monkeypatch.setattr(mod.logic_config.llm, "embedding_provider", "runpod", raising=False)
    client.runpod_api_key = "k"
    client.runpod_endpoint_id = "e"
    monkeypatch.setattr(client, "_call_runpod_embeddings", AsyncMock(side_effect=RuntimeError("boom")))
    monkeypatch.setattr(client, "_call_intelligence_api_embeddings", AsyncMock(return_value=[[1.0, 2.0]]))

    out = await client.get_embeddings(["x"], priority="high")
    assert out == [[1.0, 2.0]]


@pytest.mark.anyio
async def test_get_embeddings_together_missing_key_falls_back(monkeypatch):
    client = mod.IntelligenceAPIClient()
    monkeypatch.setattr(mod.logic_config.llm, "embedding_provider", "together", raising=False)
    client.together_api_key = None
    monkeypatch.setattr(client, "_call_intelligence_api_embeddings", AsyncMock(return_value=[[3.0]]))

    out = await client.get_embeddings(["x"], priority="high")
    assert out == [[3.0]]


@pytest.mark.anyio
async def test_intelligence_api_embeddings_exception_returns_dummy(monkeypatch):
    client = mod.IntelligenceAPIClient()
    client.intelligence_api_token = "t"
    client.intelligence_api_base = "http://x"

    req = httpx.Request("POST", "http://x/v1/embeddings")
    bad = httpx.Response(500, request=req, text="nope")
    monkeypatch.setattr(mod.httpx, "AsyncClient", lambda **_: _AsyncClientStub(bad), raising=True)

    out = await client._call_intelligence_api_embeddings(["a", "b"])
    assert out == [[0.0] * 1024, [0.0] * 1024]


@pytest.mark.anyio
async def test_rerank_low_priority_requires_db():
    client = mod.IntelligenceAPIClient()
    with pytest.raises(ValueError, match="Database session required"):
        await client.rerank("q", ["d"], priority="low", db=None)


@pytest.mark.anyio
async def test_rerank_online_exception_returns_zeroes(monkeypatch):
    client = mod.IntelligenceAPIClient()
    client.intelligence_api_token = "t"
    client.intelligence_api_base = "http://x"
    monkeypatch.setattr(mod.httpx, "AsyncClient", lambda **_: _AsyncClientStub(RuntimeError("boom")), raising=True)

    out = await client._rerank_online("q", ["a", "b"])
    assert out == [0.0, 0.0]

