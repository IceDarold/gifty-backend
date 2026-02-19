from fastapi import APIRouter, HTTPException, Depends, Request, Header
from app.config import get_settings, Settings
from app.redis_client import get_redis
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.analytics.schema import schema
from strawberry.fastapi import GraphQLRouter

async def verify_analytics_token(
    x_analytics_token: str = Header(...),
    settings: Settings = Depends(get_settings)
):
    if x_analytics_token != settings.analytics_api_token:
        raise HTTPException(status_code=403, detail="Invalid analytics token")
    return x_analytics_token

# GraphQL Context
async def get_context(
    request: Request,
    settings: Settings = Depends(get_settings),
    redis: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db)
):
    return {
        "request": request,
        "settings": settings,
        "redis": redis,
        "db": db,
    }

router = APIRouter(
    prefix="/api/v1/analytics", 
    tags=["Analytics"],
    dependencies=[Depends(verify_analytics_token)]
)

# GraphQL View
graphql_app = GraphQLRouter(schema, context_getter=get_context)

# Add GraphQL route
router.include_router(graphql_app, prefix="/graphql")
