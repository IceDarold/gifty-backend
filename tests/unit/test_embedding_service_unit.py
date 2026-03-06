from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.embeddings import EmbeddingService


@pytest.mark.anyio
async def test_embed_batch_async_empty_short_circuits(monkeypatch):
    client = SimpleNamespace(get_embeddings=AsyncMock())
    monkeypatch.setattr("app.services.embeddings.get_intelligence_client", lambda: client)

    svc = EmbeddingService(model_name="m")
    out = await svc.embed_batch_async([])
    assert out == []
    client.get_embeddings.assert_not_awaited()


@pytest.mark.anyio
async def test_embed_batch_async_calls_intelligence_client(monkeypatch):
    client = SimpleNamespace(get_embeddings=AsyncMock(return_value=[[0.0], [1.0]]))
    monkeypatch.setattr("app.services.embeddings.get_intelligence_client", lambda: client)

    svc = EmbeddingService(model_name="m")
    out = await svc.embed_batch_async(["a", "b"])
    assert out == [[0.0], [1.0]]
    client.get_embeddings.assert_awaited()


def test_embed_batch_uses_threadsafe_when_loop_is_running(monkeypatch):
    monkeypatch.setattr("app.services.embeddings.get_intelligence_client", lambda: SimpleNamespace(get_embeddings=AsyncMock()))
    svc = EmbeddingService(model_name="m")
    async def _embed(_texts):
        return [[1.0]]

    svc.embed_batch_async = _embed

    loop = SimpleNamespace(is_running=lambda: True)
    monkeypatch.setattr("asyncio.get_event_loop", lambda: loop)

    fut = SimpleNamespace(result=lambda: [[1.0]])
    def _run_coroutine_threadsafe(coro, _loop):
        coro.close()
        return fut
    monkeypatch.setattr("asyncio.run_coroutine_threadsafe", _run_coroutine_threadsafe)

    out = svc.embed_batch(["x"])
    assert out == [[1.0]]


def test_embed_batch_creates_loop_when_none(monkeypatch):
    monkeypatch.setattr("app.services.embeddings.get_intelligence_client", lambda: SimpleNamespace(get_embeddings=AsyncMock()))
    svc = EmbeddingService(model_name="m")
    async def _embed(_texts):
        return [[0.0]]

    svc.embed_batch_async = _embed

    class _Loop:
        def __init__(self):
            self._running = False

        def is_running(self):
            return self._running

        def run_until_complete(self, coro):
            # coro is an awaitable returned by AsyncMock; call via asyncio.run in real life,
            # but for unit tests we just return the configured result.
            coro.close()
            return [[0.0]]

    loop = _Loop()
    monkeypatch.setattr("asyncio.get_event_loop", lambda: (_ for _ in ()).throw(RuntimeError("no loop")))
    monkeypatch.setattr("asyncio.new_event_loop", lambda: loop)
    monkeypatch.setattr("asyncio.set_event_loop", lambda _l: None)

    out = svc.embed_batch(["x"])
    assert out == [[0.0]]
