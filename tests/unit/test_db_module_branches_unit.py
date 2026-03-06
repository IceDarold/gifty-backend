from __future__ import annotations

import builtins
import importlib.util
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


def _load_db_module_as(name: str):
    path = os.path.join(os.path.dirname(__file__), "..", "..", "app", "db.py")
    path = os.path.abspath(path)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def test_db_module_postgres_url_rewrites_and_sslmode_cleanup(monkeypatch):
    settings = SimpleNamespace(
        db_url="postgresql://u:p@supabase.local/db?sslmode=require",
        debug=False,
        redis_url="redis://localhost:6379/0",
        redis_connection_url="redis://localhost:6379/0",
    )
    monkeypatch.setattr("app.config.get_settings", lambda: settings)
    monkeypatch.delenv("TESTING", raising=False)
    import redis.asyncio as redis_asyncio
    monkeypatch.setattr(redis_asyncio, "from_url", lambda *a, **k: object())

    mod = _load_db_module_as("app_db_cov_case_postgres")
    assert "asyncpg" in mod.db_url.drivername
    assert "ssl" in mod.connect_args
    assert mod.connect_args["statement_cache_size"] == 0
    assert "sslmode" not in dict(mod.db_url.query)


@pytest.mark.anyio
async def test_db_module_testing_redis_fakeredis_importerror_falls_back(monkeypatch):
    settings = SimpleNamespace(
        db_url="sqlite+aiosqlite:///:memory:",
        debug=False,
        redis_url="redis://fallback:6379/0",
        redis_connection_url="redis://prod:6379/0",
    )
    monkeypatch.setattr("app.config.get_settings", lambda: settings)
    monkeypatch.setenv("TESTING", "true")

    import redis.asyncio as redis_asyncio
    sentinel = object()
    monkeypatch.setattr(redis_asyncio, "from_url", lambda *a, **k: sentinel)

    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.startswith("fakeredis"):
            raise ImportError("no fakeredis")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    mod = _load_db_module_as("app_db_cov_case_testing")
    assert mod.redis_client is sentinel
    assert await mod.get_redis() == sentinel


@pytest.mark.anyio
async def test_get_session_context_rolls_back_on_error(monkeypatch):
    settings = SimpleNamespace(
        db_url="sqlite+aiosqlite:///:memory:",
        debug=False,
        redis_url="redis://localhost:6379/0",
        redis_connection_url="redis://localhost:6379/0",
    )
    monkeypatch.setattr("app.config.get_settings", lambda: settings)
    monkeypatch.delenv("TESTING", raising=False)

    mod = _load_db_module_as("app_db_cov_case_session")

    session = SimpleNamespace(rollback=AsyncMock(), close=AsyncMock())

    class _SessionCM:
        async def __aenter__(self):
            return session

        async def __aexit__(self, exc_type, exc, tb):
            return None

    class _SessionLocal:
        def __call__(self):
            return _SessionCM()

    monkeypatch.setattr(mod, "SessionLocal", _SessionLocal())

    with pytest.raises(RuntimeError):
        async with mod.get_session_context():
            raise RuntimeError("boom")

    session.rollback.assert_awaited()
    session.close.assert_awaited()
