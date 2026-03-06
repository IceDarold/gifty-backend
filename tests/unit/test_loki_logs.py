from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from app.services.loki_logs import LokiLogsClient, LokiLogLine, _to_ws_url, build_logql_query


def test_to_ws_url():
    assert _to_ws_url("https://x") == "wss://x"
    assert _to_ws_url("http://x/") == "ws://x"
    assert _to_ws_url("ws://x") == "ws://x"


def test_build_logql_query_defaults_and_contains_escape():
    assert build_logql_query() == '{job="docker"}'
    q = build_logql_query(service="api", contains='a"b\\c')
    assert '{service="api"}' in q
    assert '\\"' in q
    assert "\\\\" in q


@pytest.mark.asyncio
async def test_query_range_parses_values(monkeypatch):
    class _Resp:
        content = b"1"

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "data": {
                    "result": [
                        {"stream": {"service": "api"}, "values": [["10", "l1"], ["bad", "skip"], ["20", "l2"]]},
                    ]
                }
            }

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, params=None):
            return _Resp()

    import app.services.loki_logs as mod

    monkeypatch.setattr(mod.httpx, "AsyncClient", lambda timeout=10.0: _Client())
    client = LokiLogsClient(base_url="http://loki:3100")
    out = await client.query_range(query='{job="docker"}', start_ns=0, end_ns=30, limit=10, direction="BACKWARD")
    assert [l.line for l in out] == ["l2", "l1"]
    assert out[0].labels["service"] == "api"


