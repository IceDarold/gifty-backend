from __future__ import annotations

from types import SimpleNamespace

from app.services.llm import proxy as proxy_mod


def test_build_async_client_passes_proxy(monkeypatch):
    calls = []

    class _Client:
        pass

    def _factory(*, timeout=None, proxy=None):
        calls.append({"timeout": timeout, "proxy": proxy})
        return _Client()

    monkeypatch.setattr(proxy_mod.httpx, "AsyncClient", _factory, raising=True)

    c1 = proxy_mod.build_async_client("http://proxy:1", timeout=12)
    assert isinstance(c1, _Client)
    assert calls[-1]["proxy"] == "http://proxy:1"

    c2 = proxy_mod.build_async_client(None, timeout=5)
    assert isinstance(c2, _Client)
    assert calls[-1]["proxy"] is None

