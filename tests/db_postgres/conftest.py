from __future__ import annotations

import os
import asyncio
import socket
import subprocess
import time
from typing import AsyncIterator

import pytest
import pytest_asyncio
import asyncpg
from sqlalchemy import text
from sqlalchemy.engine import make_url
from urllib.parse import quote_plus
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import sys
from pathlib import Path as _Path

ROOT = _Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from app.db import Base
from app.models import Product, ProductEmbedding


def _wait_for_port(host: str, port: int, timeout: float = 30.0) -> None:
    start = time.time()
    while time.time() - start < timeout:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            try:
                sock.connect((host, port))
                return
            except OSError:
                time.sleep(0.5)
    raise RuntimeError(f"Postgres not reachable at {host}:{port} within {timeout}s")


async def _wait_for_db(url: str, timeout: float = 30.0) -> None:
    raw = make_url(url)
    if raw.drivername == "postgresql+asyncpg":
        raw = raw.set(drivername="postgresql")
    connect_url = str(raw)
    start = time.time()
    last_exc: Exception | None = None
    while time.time() - start < timeout:
        try:
            conn = await asyncpg.connect(connect_url)
            await conn.close()
            return
        except Exception as exc:
            last_exc = exc
            await asyncio.sleep(0.5)
    raise RuntimeError(f"Postgres did not become ready in time: {last_exc}")


def _read_env_file_value(key: str) -> str | None:
    env_path = os.getenv("ENV_FILE", ".env")
    if not os.path.exists(env_path):
        return None
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                if k.strip() == key:
                    return v.strip()
    except Exception:
        return None
    return None


def _strip_quotes(value: str) -> str:
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    return value


def _get_pg_env() -> tuple[str, str, str]:
    user = os.getenv("POSTGRES_USER") or _read_env_file_value("POSTGRES_USER") or "giftyai_user"
    raw_password = os.getenv("POSTGRES_PASSWORD") or _read_env_file_value("POSTGRES_PASSWORD") or "giftyai"
    db = os.getenv("POSTGRES_DB") or _read_env_file_value("POSTGRES_DB") or "giftyai"
    return user, _strip_quotes(raw_password), db


@pytest.fixture(scope="session")
def postgres_container():
    user, password, db = _get_pg_env()
    port = int(os.getenv("POSTGRES_TEST_PORT", "5433"))
    name = os.getenv("POSTGRES_TEST_CONTAINER", "gifty-postgres-test")

    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-d",
            "--name",
            f"{name}-{port}",
            "-e",
            f"POSTGRES_USER={user}",
            "-e",
            f"POSTGRES_PASSWORD={password}",
            "-e",
            f"POSTGRES_DB={db}",
            "-e",
            "POSTGRES_HOST_AUTH_METHOD=trust",
            "-p",
            f"{port}:5432",
            "pgvector/pgvector:pg17",
        ],
        check=True,
    )
    _wait_for_port("127.0.0.1", port, timeout=60.0)
    yield

    if os.getenv("DB_TEST_KEEP_CONTAINER") == "1":
        return
    subprocess.run(["docker", "rm", "-f", f"{name}-{port}"], check=False)


def _build_local_url() -> str | None:
    user, raw_password, db = _get_pg_env()
    port = int(os.getenv("POSTGRES_TEST_PORT", "5433"))
    if user and raw_password and db:
        password = quote_plus(raw_password)
        return f"postgresql+asyncpg://{user}:{password}@127.0.0.1:{port}/{db}"
    return None


def _sanitize_url(raw: str):
    url = make_url(raw)
    if url.drivername in {"postgresql", "postgresql+psycopg2"}:
        url = url.set(drivername="postgresql+asyncpg")
    if url.query:
        url = url.set(query={})
    return url


@pytest_asyncio.fixture(scope="session")
async def postgres_db_url(postgres_container) -> str:
    local = _build_local_url()
    base_url = local or os.getenv("DATABASE_URL")
    if not base_url:
        raise RuntimeError("DATABASE_URL/POSTGRES_* are not set. Source .env before running tests.")

    url = _sanitize_url(base_url)
    db_name = f"{url.database}_test" if url.database else "giftyai_test"

    base_db_url = url
    await _wait_for_db(str(base_db_url), timeout=60.0)
    admin_url = url.set(database=url.database or "postgres")
    admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")

    async with admin_engine.begin() as conn:
        exists = await conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": db_name},
        )
        if not exists.scalar_one_or_none():
            await conn.execute(text(f"CREATE DATABASE {db_name}"))

    await admin_engine.dispose()

    test_url = str(url.set(database=db_name))
    yield test_url

    admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    async with admin_engine.begin() as conn:
        await conn.execute(
            text(
                "SELECT pg_terminate_backend(pid) "
                "FROM pg_stat_activity WHERE datname = :name"
            ),
            {"name": db_name},
        )
        await conn.execute(text(f"DROP DATABASE IF EXISTS {db_name}"))
    await admin_engine.dispose()


@pytest_asyncio.fixture
async def postgres_engine(postgres_db_url) -> AsyncIterator:
    engine = create_async_engine(postgres_db_url, future=True)

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[Product.__table__, ProductEmbedding.__table__],
        )

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def postgres_session(postgres_engine) -> AsyncIterator[AsyncSession]:
    session_factory = async_sessionmaker(postgres_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session
        await session.rollback()
