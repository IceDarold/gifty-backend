from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Request, Header
from app.config import get_settings, Settings
from app.redis_client import get_redis
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.analytics.schema import schema
from strawberry.fastapi import GraphQLRouter

async def verify_analytics_token_or_internal_auth(
    x_analytics_token: Optional[str] = Header(None),
    x_internal_token: Optional[str] = Header(None),
    x_tg_init_data: Optional[str] = Header(None),
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
):
    # 1) Preferred path for direct analytics integrations
    if x_analytics_token and x_analytics_token == settings.analytics_api_token:
        return "analytics_token"

    # 2) Fallback for admin panel / internal clients already authenticated with internal/TG auth
    from routes.internal import verify_internal_token
    await verify_internal_token(
        x_internal_token=x_internal_token,
        x_tg_init_data=x_tg_init_data,
        db=db,
    )
    return "internal_auth"

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
    dependencies=[Depends(verify_analytics_token_or_internal_auth)]
)

# REST Endpoints
@router.get("/trends", summary="Time-series trends data")
@router.get("/stats/trends", summary="Time-series trends data (alias)")
async def get_analytics_trends(
    days: int = 7,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    from app.analytics.schema import Query
    from strawberry.types import Info
    
    # We simulate GraphQL Info context
    class MockInfo:
        def __init__(self, db, redis):
            self.context = {"db": db, "redis": redis, "settings": get_settings()}

    q = Query()
    info = MockInfo(db, redis)
    trends_data = await q.trends(info, days=days)
    
    return {
        "dates": trends_data.dates,
        "dau_trend": trends_data.dau_trend,
        "quiz_starts": trends_data.quiz_starts,
        "last_updated": trends_data.last_updated
    }

@router.get("/funnel")
async def get_conversion_funnel(
    request: Request,
    settings: Settings = Depends(get_settings),
    redis: Redis = Depends(get_redis)
):
    from app.analytics.schema import query_posthog
    from datetime import datetime
    try:
        funnel_query = {
            "kind": "FunnelsQuery",
            "series": [
                {"event": "quiz_started"},
                {"event": "quiz_completed"},
                {"event": "results_shown"},
                {"event": "gift_clicked"}
            ],
            "dateRange": {"date_from": "-30d"}
        }
        
        funnel_data = await query_posthog(
            funnel_query,
            settings,
            redis,
            "analytics:full_funnel:30d",
            cache_ttl=600
        )
        
        steps = []
        results = funnel_data.get("results", [])
        if results:
            for i, step_data in enumerate(results):
                if isinstance(step_data, dict):
                    steps.append({
                        "name": step_data.get("name", f"Step {i+1}"),
                        "count": step_data.get("count", 0),
                        "conversion_rate": round(step_data.get("conversionRates", {}).get("total", 0) * 100, 2)
                    })
        
        return {
            "steps": steps,
            "last_updated": datetime.utcnow().isoformat() + "Z"
        }
    except Exception:
        return {"steps": [], "last_updated": datetime.utcnow().isoformat() + "Z"}

@router.get("/technical")
async def get_technical_stats(
    settings: Settings = Depends(get_settings),
    redis: Redis = Depends(get_redis)
):
    import httpx, json
    from datetime import datetime
    cache_key = "analytics:technical_stats"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    stats = {
        "api_health": "unknown",
        "requests_per_minute": 0,
        "error_rate_5xx": 0,
        "active_workers": 0,
        "last_errors": [],
        "last_updated": datetime.utcnow().isoformat()
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            prom_url = f"{settings.prometheus_url}/api/v1/query"
            rpm_query = 'sum(rate(http_request_duration_seconds_count[5m])) * 60'
            resp = await client.get(prom_url, params={"query": rpm_query})
            if resp.status_code == 200:
                results = resp.json().get("data", {}).get("result", [])
                if results:
                    stats["requests_per_minute"] = round(float(results[0]["value"][1]), 2)
                    stats["api_health"] = "healthy"

            err_query = 'sum(rate(http_request_duration_seconds_count{status=~"5.."}[5m]))'
            resp = await client.get(prom_url, params={"query": err_query})
            if resp.status_code == 200:
                results = resp.json().get("data", {}).get("result", [])
                if results:
                    stats["error_rate_5xx"] = round(float(results[0]["value"][1]), 4)
        except Exception as e:
            stats["api_health"] = f"error: {str(e)}"

        try:
            loki_url = f"{settings.loki_url}/loki/api/v1/query_range"
            loki_query = '{job=~".+"} |= "error" or "exception"'
            params = {"query": loki_query, "limit": 5, "direction": "backward"}
            resp = await client.get(loki_url, params=params)
            if resp.status_code == 200:
                results = resp.json().get("data", {}).get("result", [])
                logs = []
                for stream in results:
                    for val in stream.get("values", []):
                        logs.append(val[1][:200] + "..." if len(val[1]) > 200 else val[1])
                stats["last_errors"] = logs[:5]
        except Exception: pass

    await redis.setex(cache_key, 60, json.dumps(stats))
    return stats

@router.get("/scraping")
async def get_scraping_monitoring(
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db)
):
    from sqlalchemy import select, func
    from app.models import CategoryMap, ParsingSource
    import httpx
    
    sources_stmt = select(func.count(ParsingSource.id)).where(ParsingSource.is_active == True)
    sources_count = (await db.execute(sources_stmt)).scalar() or 0
    
    unmapped_stmt = select(func.count(CategoryMap.id)).where(CategoryMap.internal_category_id == None)
    unmapped_count = (await db.execute(unmapped_stmt)).scalar() or 0
    
    scraping_stats = {
        "active_sources": sources_count,
        "unmapped_categories": unmapped_count,
        "total_scraped_items": 0,
        "ingestion_errors": 0,
        "spiders": {}
    }
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            prom_url = f"{settings.prometheus_url}/api/v1/query"
            
            items_query = 'sum(scraped_items_total)'
            resp = await client.get(prom_url, params={"query": items_query})
            if resp.status_code == 200:
                results = resp.json().get("data", {}).get("result", [])
                if results:
                    scraping_stats["total_scraped_items"] = int(float(results[0]["value"][1]))

            errors_query = 'sum(ingestion_batches_total{status="error"})'
            resp = await client.get(prom_url, params={"query": errors_query})
            if resp.status_code == 200:
                results = resp.json().get("data", {}).get("result", [])
                if results:
                    scraping_stats["ingestion_errors"] = int(float(results[0]["value"][1]))

            spider_query = 'sum by (spider) (scraped_items_total)'
            resp = await client.get(prom_url, params={"query": spider_query})
            if resp.status_code == 200:
                for res in resp.json().get("data", {}).get("result", []):
                    spider_name = res["metric"]["spider"]
                    scraping_stats["spiders"][spider_name] = {
                        "items_scraped": int(float(res["value"][1]))
                    }
        except Exception: pass

    return scraping_stats

# GraphQL View
graphql_app = GraphQLRouter(schema, context_getter=get_context)

# Add GraphQL route
router.include_router(graphql_app, prefix="/graphql")
