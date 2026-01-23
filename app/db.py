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


db_url = make_url(settings.database_url)
connect_args = {}

if db_url.drivername in {"postgresql", "postgresql+psycopg2"}:
    db_url = db_url.set(drivername="postgresql+asyncpg")

# Supabase and Render require SSL. 
# asyncpg uses 'ssl' parameter instead of 'sslmode'
if "sslmode" in db_url.query:
    ssl_mode = db_url.query.get("sslmode")
    if ssl_mode == "require":
        connect_args["ssl"] = True
    # We remove sslmode from query to avoid asyncpg confusing it with its own parameters
    query = dict(db_url.query)
    query.pop("sslmode", None)
    db_url = db_url.set(query=query)

engine = create_async_engine(
    db_url, 
    echo=False, 
    pool_pre_ping=True,
    connect_args=connect_args
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session


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

