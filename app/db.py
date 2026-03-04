from __future__ import annotations

from contextlib import asynccontextmanager
from sqlalchemy import MetaData
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=convention)


import ssl
import os

db_url = make_url(settings.db_url)
# Startup diagnostic print
print(f"DEBUG_DB: Driver={db_url.drivername}, Host={db_url.host}, DB={db_url.database}")
print(f"DEBUG_DB: User={db_url.username}, Params={db_url.query}")

connect_args = {}

if db_url.drivername in {"postgresql", "postgresql+psycopg2"}:
    db_url = db_url.set(drivername="postgresql+asyncpg")

# Supabase Pooler (and Render) specific configuration
# asyncpg uses 'ssl' instead of 'sslmode'
if "sslmode" in db_url.query or "supabase" in str(db_url.host):
    # Create a custom SSL context that accepts self-signed certs
    # This is often needed for Supabase Pooler connections
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    connect_args["ssl"] = ssl_context
    
    # CRITICAL for Supabase Pooler (Transaction Mode / port 6543)
    # and highly recommended for session mode stability on Render:
    # Disable prepared statements as they are not supported by most poolers.
    connect_args["statement_cache_size"] = 0
    connect_args["prepared_statement_cache_size"] = 0
    
    # Clean up sslmode from URL to avoid asyncpg warnings
    query = dict(db_url.query)
    query.pop("sslmode", None)
    db_url = db_url.set(query=query)

engine_args = {
    "echo": settings.debug,
    "connect_args": connect_args
}

# SQLite doesn't support pool_size and max_overflow
if "sqlite" not in db_url.drivername:
    pool_size = int(os.getenv("DB_POOL_SIZE", "20"))
    max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "20"))
    pool_timeout = int(os.getenv("DB_POOL_TIMEOUT", "30"))
    engine_args.update({
        "pool_pre_ping": True,
        "pool_size": pool_size,
        "max_overflow": max_overflow,
        "pool_timeout": pool_timeout,
    })

engine = create_async_engine(db_url, **engine_args)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session


import redis.asyncio as redis

# Redis setup
if os.getenv("TESTING") == "true":
    # Use fakeredis for testing
    try:
        from fakeredis import aioredis as fakeredis
        redis_client = fakeredis.FakeRedis(decode_responses=True)
    except ImportError:
        # Fallback if fakeredis not available
        redis_client = redis.from_url(settings.redis_url, decode_responses=True)
else:
    redis_client = redis.from_url(settings.redis_connection_url, decode_responses=True)

async def get_redis():
    """Returns a redis client connection."""
    return redis_client


@asynccontextmanager
async def get_session_context() -> AsyncSession:
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
