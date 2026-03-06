from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.ai_reasoning_service import AIReasoningService, _redact_text
from app.services.llm.interface import LLMResponse, Message


class _BadRaw:
    def __getattr__(self, _name):
        raise RuntimeError("no attrs")


@pytest.mark.anyio
async def test_log_call_handles_provider_request_id_extraction_failure_and_db_errors(monkeypatch):
    from app.services import ai_reasoning_service as mod

    fake_llm = SimpleNamespace()
    monkeypatch.setattr(mod.LLMFactory, "get_client", lambda: fake_llm, raising=True)
    monkeypatch.setattr(mod, "estimate_cost", AsyncMock(return_value=0.0), raising=True)

    db = SimpleNamespace(add=lambda _x: None, commit=AsyncMock())
    svc = AIReasoningService(db=db)

    resp = LLMResponse(content="x", raw_response=_BadRaw(), usage={"prompt_tokens": 1, "completion_tokens": 2})
    await svc._log_call(
        call_type="t",
        model="m",
        response=resp,
        latency_ms=1,
        messages=[Message(role="user", content="u")],
        system_prompt="s",
        session_id="sid",
        params={"k": "v"},
    )

    svc.db = SimpleNamespace(add=lambda _x: None, commit=AsyncMock(side_effect=RuntimeError("db")))
    await svc._log_call(
        call_type="t",
        model="m",
        response=resp,
        latency_ms=1,
        messages=[Message(role="user", content="authorization: bearer sk-123")],
        system_prompt="s",
        session_id="sid",
        error_message="authorization: bearer sk-123",
    )


@pytest.mark.anyio
async def test_generate_with_logging_applies_smart_model_override(monkeypatch):
    from app.services import ai_reasoning_service as mod

    fake_llm = SimpleNamespace(generate_text=AsyncMock(return_value=LLMResponse(content='{"ok": true}', raw_response={"id": "r"}, usage={})))
    monkeypatch.setattr(mod.LLMFactory, "get_client", lambda: fake_llm, raising=True)
    monkeypatch.setattr(mod.ExperimentService, "get_overrides", lambda _sid: {"llm_model_smart": "override", "_experiment_id": "e", "_variant_id": "v"}, raising=True)

    svc = AIReasoningService(db=None)
    out = await svc._generate_with_logging(
        call_type="x",
        model=svc.model_smart,
        system_prompt="s",
        messages=[Message(role="user", content='{"a": 1}')],
        session_id="sid",
    )
    assert out["ok"] is True
    assert fake_llm.generate_text.await_args.kwargs["model"] == "override"


@pytest.mark.anyio
async def test_normalize_topics_empty_returns_empty_list(monkeypatch):
    from app.services import ai_reasoning_service as mod

    monkeypatch.setattr(mod.LLMFactory, "get_client", lambda: SimpleNamespace(), raising=True)
    svc = AIReasoningService(db=None)
    assert await svc.normalize_topics([]) == []


@pytest.mark.anyio
async def test_prompt_builders_cover_personalized_probe_bulk_and_hints(monkeypatch):
    from app.services import ai_reasoning_service as mod

    monkeypatch.setattr(mod.LLMFactory, "get_client", lambda: SimpleNamespace(), raising=True)

    def _prompt(name: str) -> str:
        if name == "system":
            return "SYS {language}"
        if name.startswith("personalized_probe_"):
            return "Topic: {topic} Quiz: {quiz_json}"
        if name == "generate_hypotheses_bulk":
            return "Topics: {topics_str} Quiz: {quiz_json} Like: {liked_concepts} Dislike: {disliked_concepts} Lang: {language}"
        if name == "generate_topic_hints":
            return "Quiz: {quiz_json} Topics: {topics_explored}"
        return "{x}"

    monkeypatch.setattr(mod.registry, "get_prompt", _prompt, raising=True)

    svc = AIReasoningService(db=None)
    svc._generate_with_logging = AsyncMock(return_value={"hints": [{"q": "?"}]})

    await svc.generate_personalized_probe("foo", quiz_data={"a": 1}, topic=None, session_id="sid")
    await svc.generate_hypotheses_bulk(["t1"], quiz_data={"b": 2}, session_id="sid")
    hints = await svc.generate_topic_hints(quiz_data={"c": 3}, topics_explored=["x"], session_id="sid")
    assert hints == [{"q": "?"}]


@pytest.mark.anyio
async def test_extract_json_and_sanitize_helpers_cover_error_branches(monkeypatch):
    from app.services import ai_reasoning_service as mod

    monkeypatch.setattr(mod.LLMFactory, "get_client", lambda: SimpleNamespace(), raising=True)
    svc = AIReasoningService(db=None)

    out = await svc._extract_json("{not valid json")
    assert out == {}

    assert svc._sanitize_input("") == ""
    assert svc._sanitize_dict({"x": 1})["x"] == 1
    assert _redact_text(123) == "123"

