import os
import yaml
import pytest
from pathlib import Path

def pytest_configure(config):
    # Register custom markers
    config.addinivalue_line("markers", "ai_test: AI intelligence tests")
    config.addinivalue_line("markers", "slow: slow running tests")

def get_test_config():
    config_path = Path(__file__).parent.parent / "tests_config.yaml"
    if not config_path.exists():
        return {}
    with open(config_path, "r") as f:
        return yaml.safe_load(f) or {}

def pytest_collection_modifyitems(config, items):
    test_cfg = get_test_config()
    groups = test_cfg.get("test_groups", {})
    
    tests_root = Path(__file__).parent.parent / "tests"
    for item in items:
        # Get absolute path of the test file
        item_path = Path(str(item.fspath))
        
        try:
            rel_path = item_path.relative_to(tests_root)
            group_name = rel_path.parts[0] if rel_path.parts else "root"
        except ValueError:
            # File is outside the 'tests' directory
            group_name = "other"
        
        # Mapping root-level files to 'security' group for example
        if group_name.startswith("test_"):
             group_name = "security" if "security" in group_name or "pkce" in group_name or "state" in group_name else "core"

        if group_name in groups and not groups[group_name]:
            item.add_marker(pytest.mark.skip(reason=f"Group '{group_name}' is disabled in tests_config.yaml"))
            continue


# --- Postgres Fixtures (Moved from tests/db_postgres/conftest.py) ---
import pytest_asyncio
import asyncio
import pytest




import socket
import subprocess
import time
from typing import AsyncIterator, Optional
import asyncpg
from sqlalchemy import text
from sqlalchemy.engine import make_url
from urllib.parse import quote_plus
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
import sys
from pathlib import Path as _Path

ROOT = _Path(__file__).resolve().parents[1]
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
                sock.connect(("localhost", port))
                return
            except OSError:
                time.sleep(0.5)
    raise RuntimeError(f"Postgres not reachable at localhost:{port} within {timeout}s")


async def _wait_for_db(url: str, timeout: float = 30.0) -> None:
    raw = make_url(url)
    if raw.drivername == "postgresql+asyncpg":
        raw = raw.set(drivername="postgresql")
    connect_url = raw.render_as_string(hide_password=False)
    print(f"DEBUG: _wait_for_db connecting to: {connect_url}")
    start = time.time()
    last_exc: Optional[Exception] = None
    while time.time() - start < timeout:
        try:
            conn = await asyncpg.connect(connect_url)
            await conn.close()
            return
        except Exception as exc:
            print(f"DEBUG: Connection attempt failed: {exc}") # Added
            last_exc = exc
            await asyncio.sleep(0.5)
    raise RuntimeError(f"Postgres did not become ready in time: {last_exc}")


def _read_env_file_value(key: str) -> Optional[str]:
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
    password = os.getenv("POSTGRES_PASSWORD") or _read_env_file_value("POSTGRES_PASSWORD") or "kG7pZ3vQ2mL9sT4xN8wC"
    db = os.getenv("POSTGRES_DB") or _read_env_file_value("POSTGRES_DB") or "giftyai"
    return user, _strip_quotes(password), db


@pytest.fixture(scope="session")
def postgres_container():
    # Only run if we actually intend to use a local Postgres (not SQLite or other)
    db_url = os.getenv("DATABASE_URL")
    if db_url and "sqlite" in db_url:
         print("DEBUG: Using SQLite, skipping postgres_container fixture")
         yield
         return

    user, password, db = _get_pg_env()
    # PREFER PORT 5432 (Existing Dev Container)
    port = int(os.getenv("POSTGRES_TEST_PORT", "5432"))
    name = os.getenv("POSTGRES_TEST_CONTAINER", "gifty-postgres-test")

    # Check if port is open by trying a low-level socket connect
    is_open = False
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    try:
        result = sock.connect_ex(("127.0.0.1", port))
        if result == 0:
            is_open = True
    except:
        pass
    finally:
        sock.close()

    if is_open:
        print(f"REUSING existing Postgres on port {port}")
        os.environ["POSTGRES_TEST_PORT"] = str(port)
        yield
        return

    # Fallback: Try to start container
    if port == 5432:
        port = 5433 

    try:
        subprocess.run(["docker", "rm", "-f", f"{name}-{port}"], check=False, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    except:
        pass

    print(f"Starting new Postgres container on port {port}...")
    try:
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
                "-c", "fsync=off", "-c", "full_page_writes=off" 
            ],
            check=True,
        )
        _wait_for_port("127.0.0.1", port, timeout=60.0)
        os.environ["POSTGRES_TEST_PORT"] = str(port)
    except Exception as e:
        print(f"Failed to start Docker container: {e}. Tests might fail if no DB is reachable.")
    
    yield
    subprocess.run(["docker", "rm", "-f", f"{name}-{port}"], check=False, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)




def _build_local_url() -> Optional[str]:
    user, raw_password, db = _get_pg_env()
    port = int(os.getenv("POSTGRES_TEST_PORT", "5432")) # Default to 5432
    if user and raw_password and db:
        password = quote_plus(raw_password)
        return f"postgresql+asyncpg://{user}:{password}@localhost:{port}/{db}"
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
    db_url = os.getenv("DATABASE_URL")
    if db_url and "sqlite" in db_url:
        print(f"DEBUG: Using SQLite URL: {db_url}")
        yield db_url
        return

    local = _build_local_url()
    base_url = local or db_url
    if not base_url:
        raise RuntimeError("DATABASE_URL/POSTGRES_* are not set. Source .env before running tests.")

    url = _sanitize_url(base_url)
    db_name = f"{url.database}_test" if url.database else "giftyai_test"

    base_db_url = url.render_as_string(hide_password=False)
    await _wait_for_db(base_db_url, timeout=60.0)
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

    test_url = url.set(database=db_name).render_as_string(hide_password=False)
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
        # Create ALL tables
        await conn.run_sync(Base.metadata.create_all)

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def postgres_session(postgres_engine) -> AsyncIterator[AsyncSession]:
    session_factory = async_sessionmaker(postgres_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session
        await session.rollback()
