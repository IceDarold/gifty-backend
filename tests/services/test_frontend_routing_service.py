from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import Base
from app.models import (
    FrontendAllowedHost,
    FrontendApp,
    FrontendProfile,
    FrontendRelease,
    FrontendRule,
    FrontendRuntimeState,
)
from app.schemas.frontend import FrontendConfigRequest
from app.services.frontend_routing import FrontendRoutingService


class FakeRedis:
    def __init__(self):
        self.store = {}

    async def get(self, key: str):
        return self.store.get(key)

    async def setex(self, key: str, ttl: int, value: str):
        self.store[key] = value

    async def scan(self, cursor=0, match=None, count=200):
        keys = list(self.store.keys())
        if match:
            prefix = match.replace("*", "")
            keys = [k for k in keys if k.startswith(prefix)]
        return 0, keys

    async def delete(self, *keys):
        for key in keys:
            self.store.pop(key, None)


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                FrontendApp.__table__,
                FrontendRelease.__table__,
                FrontendProfile.__table__,
                FrontendRule.__table__,
                FrontendRuntimeState.__table__,
                FrontendAllowedHost.__table__,
            ],
        )
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def _seed(session: AsyncSession):
    app = FrontendApp(key="product", name="Product", is_active=True)
    profile = FrontendProfile(key="main", name="Main", is_active=True)
    session.add_all([app, profile])
    await session.flush()

    rel_healthy = FrontendRelease(
        app_id=app.id,
        version="v55",
        target_url="https://product.vercel.app",
        status="ready",
        health_status="healthy",
        flags={"base": True},
    )
    rel_campaign = FrontendRelease(
        app_id=app.id,
        version="v99",
        target_url="https://campaign.vercel.app",
        status="ready",
        health_status="healthy",
        flags={"promo": "default"},
    )
    rel_unhealthy = FrontendRelease(
        app_id=app.id,
        version="v10",
        target_url="https://bad.vercel.app",
        status="ready",
        health_status="unhealthy",
        flags={},
    )
    session.add_all([rel_healthy, rel_campaign, rel_unhealthy])
    await session.flush()

    session.add_all(
        [
            FrontendRule(
                profile_id=profile.id,
                priority=200,
                host_pattern="giftyai.ru",
                path_pattern="/products",
                query_conditions={"utm_campaign": "blackfriday"},
                target_release_id=rel_campaign.id,
                flags_override={"promo": "blackfriday"},
                is_active=True,
            ),
            FrontendRule(
                profile_id=profile.id,
                priority=100,
                host_pattern="giftyai.ru",
                path_pattern="/product",
                query_conditions={},
                target_release_id=rel_healthy.id,
                flags_override={},
                is_active=True,
            ),
        ]
    )
    session.add(
        FrontendRuntimeState(
            id=1,
            active_profile_id=profile.id,
            fallback_release_id=rel_healthy.id,
            sticky_enabled=True,
            sticky_ttl_seconds=1800,
            cache_ttl_seconds=15,
        )
    )
    session.add(FrontendAllowedHost(host="product.vercel.app", is_active=True))
    session.add(FrontendAllowedHost(host="campaign.vercel.app", is_active=True))
    await session.commit()


@pytest.mark.asyncio
async def test_resolve_by_query_rule(db_session: AsyncSession):
    await _seed(db_session)
    service = FrontendRoutingService(db_session, redis=FakeRedis())

    result = await service.resolve_config(
        FrontendConfigRequest(
            host="giftyai.ru",
            path="/products",
            query_params={"utm_campaign": "blackfriday"},
        )
    )

    assert result["release_id"] > 0
    assert "campaign.vercel.app" in result["target_url"]
    assert result["flags"]["promo"] == "blackfriday"
    assert result["fallback_used"] is False


@pytest.mark.asyncio
async def test_sticky_release_wins(db_session: AsyncSession):
    await _seed(db_session)
    service = FrontendRoutingService(db_session, redis=FakeRedis())

    # release #1 and #2 are inserted in seed; pick v55 by path first
    first = await service.resolve_config(
        FrontendConfigRequest(host="giftyai.ru", path="/product", query_params={})
    )
    sticky_id = first["release_id"]

    second = await service.resolve_config(
        FrontendConfigRequest(host="giftyai.ru", path="/products", query_params={"utm_campaign": "blackfriday"}, sticky_release_id=sticky_id)
    )

    assert second["release_id"] == sticky_id
    assert second["sticky_used"] is True


@pytest.mark.asyncio
async def test_fallback_when_no_match(db_session: AsyncSession):
    await _seed(db_session)
    service = FrontendRoutingService(db_session, redis=FakeRedis())

    result = await service.resolve_config(
        FrontendConfigRequest(host="giftyai.ru", path="/unknown", query_params={})
    )

    assert result["fallback_used"] is True
    assert "product.vercel.app" in result["target_url"]
