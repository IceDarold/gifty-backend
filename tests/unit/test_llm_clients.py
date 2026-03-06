from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.llm.interface import Message


class _FakeResp:
    def __init__(self, status_code: int, payload: dict, *, raise_for_status: Exception | None = None):
        self.status_code = status_code
        self._payload = payload
        self._raise = raise_for_status
        self.content = b"1"

    def raise_for_status(self):
        if self._raise:
            raise self._raise

    def json(self):
        return self._payload


class _FakeAsyncClient:
    def __init__(self, resp: _FakeResp):
        self._resp = resp
        self.post_calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json=None, headers=None):
        self.post_calls.append({"url": url, "json": json, "headers": headers})
        return self._resp


@pytest.mark.asyncio
async def test_groq_client_builds_payload_and_parses_usage(monkeypatch):
    from app.services.llm import groq_client as mod
    import httpx

    monkeypatch.setattr(mod, "get_settings", lambda: SimpleNamespace(groq_api_key="k", llm_proxy_url=None), raising=True)
    resp = _FakeResp(
        200,
        {"choices": [{"message": {"content": "hi"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 2}},
    )
    client = _FakeAsyncClient(resp)
    monkeypatch.setattr(mod, "build_async_client", lambda proxy_url: client, raising=True)

    out = await mod.GroqClient().generate_text(
        messages=[Message(role="user", content="u")],
        model="claude-3-haiku-20240307",
        system_prompt="s",
        stops=["x"],
        json_mode=True,
    )
    assert out.content == "hi"
    assert out.usage["input_tokens"] == 1
    assert client.post_calls[0]["json"]["response_format"]["type"] == "json_object"


@pytest.mark.asyncio
async def test_openrouter_client_retries_on_429(monkeypatch):
    from app.services.llm import openrouter_client as mod
    import httpx

    monkeypatch.setattr(mod, "get_settings", lambda: SimpleNamespace(openrouter_api_key="k", llm_proxy_url=None), raising=True)

    class _HTTPStatusError(httpx.HTTPStatusError):
        pass

    # First call: 429, second: ok
    err_resp = httpx.Response(429, request=httpx.Request("POST", "x"))
    ok_resp = _FakeResp(200, {"choices": [{"message": {"content": "ok"}}], "usage": {}})

    class _Client:
        def __init__(self):
            self.calls = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise httpx.HTTPStatusError("rate", request=err_resp.request, response=err_resp)
            return ok_resp

    client = _Client()
    monkeypatch.setattr(mod, "build_async_client", lambda proxy_url: client, raising=True)
    monkeypatch.setattr(asyncio, "sleep", AsyncMock(), raising=True)

    out = await mod.OpenRouterClient().generate_text(messages=[Message(role="user", content="u")], model="claude-opus-4-6")
    assert out.content == "ok"
    assert client.calls == 2


@pytest.mark.asyncio
async def test_together_client_error_propagates(monkeypatch):
    from app.services.llm import together_client as mod
    import httpx

    monkeypatch.setattr(mod, "get_settings", lambda: SimpleNamespace(together_api_key="k", llm_proxy_url=None), raising=True)
    err_resp = httpx.Response(400, request=httpx.Request("POST", "x"))
    client = _FakeAsyncClient(_FakeResp(400, {}, raise_for_status=httpx.HTTPStatusError("bad", request=err_resp.request, response=err_resp)))
    monkeypatch.setattr(mod.httpx, "AsyncClient", lambda timeout=60: client, raising=True)

    with pytest.raises(httpx.HTTPStatusError):
        await mod.TogetherClient().generate_text(messages=[Message(role="user", content="u")], model="claude-3-haiku-20240307")


@pytest.mark.asyncio
async def test_anthropic_client_passes_system_and_stops(monkeypatch):
    from app.services.llm import anthropic_client as mod

    created = {}

    class _Messages:
        async def create(self, **kwargs):
            created.update(kwargs)
            return SimpleNamespace(
                content=[SimpleNamespace(text="hi")],
                usage=SimpleNamespace(input_tokens=1, output_tokens=2),
            )

    class _AsyncAnthropic:
        def __init__(self, api_key=None, http_client=None):
            self.messages = _Messages()

    monkeypatch.setattr(mod, "AsyncAnthropic", _AsyncAnthropic, raising=True)
    monkeypatch.setattr(mod, "get_settings", lambda: SimpleNamespace(anthropic_api_key="k", llm_proxy_url=None), raising=True)
    monkeypatch.setattr(mod, "build_async_client", lambda proxy_url: None, raising=True)

    out = await mod.AnthropicClient().generate_text(
        messages=[Message(role="user", content="u")],
        model="claude",
        system_prompt="s",
        stops=["x"],
    )
    assert out.content == "hi"
    assert created["system"] == "s"
    assert created["stop_sequences"] == ["x"]


@pytest.mark.asyncio
async def test_gemini_client_builds_config_and_retries(monkeypatch):
    from app.services.llm import gemini_client as mod

    # Minimal stubs for google.genai types
    class _Config:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.response_mime_type = None

    class _Part:
        def __init__(self, text: str):
            self.text = text

    class _Content:
        def __init__(self, role: str, parts):
            self.role = role
            self.parts = parts

    class _ClientError(Exception):
        def __init__(self, code):
            super().__init__("err")
            self.code = code

    class _Models:
        def __init__(self):
            self.calls = 0

        def generate_content(self, model=None, contents=None, config=None):
            self.calls += 1
            if self.calls == 1:
                raise _ClientError(429)
            return SimpleNamespace(
                text="ok",
                usage_metadata=SimpleNamespace(prompt_token_count=1, candidates_token_count=2),
            )

    class _GenAIClient:
        def __init__(self, api_key=None):
            self.models = _Models()

    monkeypatch.setattr(mod, "get_settings", lambda: SimpleNamespace(gemini_api_key="k"), raising=True)
    monkeypatch.setattr(mod, "genai", SimpleNamespace(Client=_GenAIClient), raising=True)
    monkeypatch.setattr(mod, "types", SimpleNamespace(GenerateContentConfig=_Config, Content=_Content, Part=_Part), raising=True)
    monkeypatch.setattr(mod, "ClientError", _ClientError, raising=True)
    monkeypatch.setattr(asyncio, "sleep", AsyncMock(), raising=True)

    out = await mod.GeminiClient().generate_text(
        messages=[Message(role="user", content="u")],
        model="claude-3-haiku-20240307",
        json_mode=True,
    )
    assert out.content == "ok"


def test_openrouter_client_requires_api_key(monkeypatch):
    from app.services.llm import openrouter_client as mod

    monkeypatch.setattr(mod, "get_settings", lambda: SimpleNamespace(openrouter_api_key=None, llm_proxy_url=None), raising=True)
    with pytest.raises(ValueError):
        mod.OpenRouterClient()
