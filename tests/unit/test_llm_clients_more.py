from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from app.services.llm.interface import Message


class _AsyncClientStub:
    def __init__(self, responses_or_exc):
        self._queue = list(responses_or_exc)
        self.last_request = None
        self.last_json = None
        self.last_headers = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, *, json=None, headers=None):
        self.last_request = url
        self.last_json = json
        self.last_headers = headers
        item = self._queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.mark.anyio
async def test_together_client_init_requires_api_key(monkeypatch):
    from app.services.llm import together_client as mod

    monkeypatch.setattr(mod, "get_settings", lambda: SimpleNamespace(together_api_key=None), raising=True)
    with pytest.raises(ValueError, match="TOGETHER_API_KEY"):
        mod.TogetherClient()


@pytest.mark.anyio
async def test_together_client_generate_text_builds_payload_and_parses_response(monkeypatch):
    from app.services.llm import together_client as mod

    monkeypatch.setattr(mod, "get_settings", lambda: SimpleNamespace(together_api_key="k"), raising=True)

    req = httpx.Request("POST", mod.TOGETHER_API_BASE)
    ok = httpx.Response(
        200,
        request=req,
        json={"choices": [{"message": {"content": "hi"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 2}},
    )
    stub = _AsyncClientStub([ok])
    monkeypatch.setattr(mod.httpx, "AsyncClient", lambda **_: stub, raising=True)

    client = mod.TogetherClient()
    out = await client.generate_text(
        messages=[Message(role="user", content="u")],
        model="claude-3-haiku-20240307",
        system_prompt="s",
        stops=["\n\n"],
        json_mode=True,
    )
    assert out.content == "hi"
    assert stub.last_json["stop"] == ["\n\n"]
    assert stub.last_json["response_format"] == {"type": "json_object"}


@pytest.mark.anyio
async def test_together_client_retries_on_429(monkeypatch):
    from app.services.llm import together_client as mod

    monkeypatch.setattr(mod, "get_settings", lambda: SimpleNamespace(together_api_key="k"), raising=True)
    monkeypatch.setattr(mod.asyncio, "sleep", AsyncMock(), raising=True)

    req = httpx.Request("POST", mod.TOGETHER_API_BASE)
    rate_limited = httpx.Response(429, request=req, text="rl")
    ok = httpx.Response(200, request=req, json={"choices": [{"message": {"content": "ok"}}], "usage": {}})
    stub = _AsyncClientStub([rate_limited, ok])
    monkeypatch.setattr(mod.httpx, "AsyncClient", lambda **_: stub, raising=True)

    client = mod.TogetherClient()
    out = await client.generate_text(messages=[Message(role="user", content="u")], model="x")
    assert out.content == "ok"
    assert mod.asyncio.sleep.await_count == 1


@pytest.mark.anyio
async def test_together_client_raises_on_unexpected_error_after_retries(monkeypatch):
    from app.services.llm import together_client as mod

    monkeypatch.setattr(mod, "get_settings", lambda: SimpleNamespace(together_api_key="k"), raising=True)
    boom = RuntimeError("boom")
    stub = _AsyncClientStub([boom, boom, boom])
    monkeypatch.setattr(mod.httpx, "AsyncClient", lambda **_: stub, raising=True)

    client = mod.TogetherClient()
    with pytest.raises(RuntimeError, match="boom"):
        await client.generate_text(messages=[Message(role="user", content="u")], model="x")


@pytest.mark.anyio
async def test_groq_client_init_requires_api_key(monkeypatch):
    from app.services.llm import groq_client as mod

    monkeypatch.setattr(mod, "get_settings", lambda: SimpleNamespace(groq_api_key=None, llm_proxy_url=None), raising=True)
    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        mod.GroqClient()


@pytest.mark.anyio
async def test_groq_client_retries_on_429_and_then_raises_last_error(monkeypatch):
    from app.services.llm import groq_client as mod

    monkeypatch.setattr(mod, "get_settings", lambda: SimpleNamespace(groq_api_key="k", llm_proxy_url=None), raising=True)
    monkeypatch.setattr(mod.asyncio, "sleep", AsyncMock(), raising=True)

    req = httpx.Request("POST", mod.GROQ_API_BASE)
    rate_limited = httpx.Response(429, request=req, text="rl")

    class _ClientCM:
        def __init__(self):
            self.client = _AsyncClientStub([rate_limited, rate_limited, rate_limited])

        async def __aenter__(self):
            return self.client

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(mod, "build_async_client", lambda *_args, **_kwargs: _ClientCM(), raising=True)

    client = mod.GroqClient()
    with pytest.raises(httpx.HTTPStatusError):
        await client.generate_text(messages=[Message(role="user", content="u")], model="claude-3-haiku-20240307")
    assert mod.asyncio.sleep.await_count >= 1


def test_proxy_helper_get_proxy_transport_branches(caplog):
    from app.services.llm import proxy as mod

    assert mod.get_proxy_transport(None) is None
    assert mod.get_proxy_transport("http://127.0.0.1:1") is None

