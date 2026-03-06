from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.loki_logs import LokiLogsClient, _now_ns, build_logql_query


@pytest.mark.anyio
async def test_label_values_filters_and_casts(monkeypatch):
    class _Resp:
        def __init__(self):
            self.content = b"1"

        def raise_for_status(self):
            return None

        def json(self):
            return {"data": ["a", None, 1, ""]}

    client = SimpleNamespace(get=AsyncMock(return_value=_Resp()))

    class _CM:
        async def __aenter__(self):
            return client

        async def __aexit__(self, exc_type, exc, tb):
            return None

    monkeypatch.setattr("httpx.AsyncClient", lambda timeout=6.0: _CM())

    loki = LokiLogsClient(base_url="http://loki:3100")
    out = await loki.label_values("service")
    assert out == ["a", "1"]


@pytest.mark.anyio
async def test_query_range_parses_streams_and_sorts(monkeypatch):
    payload = {
        "data": {
            "result": [
                {"stream": {"service": "x"}, "values": [["2", "b"], ["1", "a"], ["bad", "skip"]]},
            ]
        }
    }

    class _Resp:
        content = b"1"

        def raise_for_status(self):
            return None

        def json(self):
            return payload

    client = SimpleNamespace(get=AsyncMock(return_value=_Resp()))

    class _CM:
        async def __aenter__(self):
            return client

        async def __aexit__(self, exc_type, exc, tb):
            return None

    monkeypatch.setattr("httpx.AsyncClient", lambda timeout=10.0: _CM())

    loki = LokiLogsClient(base_url="http://loki:3100")
    out = await loki.query_range(query="{x}", start_ns=0, end_ns=10, direction="FORWARD")
    assert [line.line for line in out] == ["a", "b"]


@pytest.mark.anyio
async def test_tail_yields_lines_and_handles_bad_frames(monkeypatch):
    # Cover: _now_ns, invalid json, bad ts fallback.
    ns = _now_ns()
    frames = [
        "",  # ignored
        "{bad-json",  # ignored
        json.dumps({"streams": [{"stream": {"service": "x"}, "values": [["bad", "a"], [str(ns), "b"]]}]}),
    ]

    class _WS:
        def __init__(self):
            self._i = 0

        async def recv(self):
            if self._i >= len(frames):
                raise asyncio.CancelledError()
            v = frames[self._i]
            self._i += 1
            return v

    import asyncio

    ws = _WS()

    class _CM:
        async def __aenter__(self):
            return ws

        async def __aexit__(self, exc_type, exc, tb):
            return None

    monkeypatch.setattr("websockets.connect", lambda *a, **k: _CM())

    loki = LokiLogsClient(base_url="http://loki:3100")
    gen = loki.tail(query='{service="x"}', limit=2)

    # First yielded line uses fallback ts (now_ns) when ts can't be parsed.
    first = await gen.__anext__()
    assert first.line == "a"
    assert isinstance(first.ts_ns, int)

    second = await gen.__anext__()
    assert second.line == "b"
    await gen.aclose()


def test_build_logql_query_variants():
    assert build_logql_query() == '{job="docker"}'
    assert build_logql_query(service="api", container="c") == '{service="api",container="c"}'
    assert build_logql_query(service="api", contains='a"b') == '{service="api"} |= "a\\"b"'
