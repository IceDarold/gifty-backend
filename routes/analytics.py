from fastapi import APIRouter, HTTPException, Depends, Request, Header
from typing import Dict, Any, List
import httpx
from datetime import datetime, timedelta
from app.config import get_settings, Settings
from app.redis_client import get_redis
from redis.asyncio import Redis
import json

POSTHOG_API_BASE = "https://app.posthog.com/api"


async def verify_analytics_token(
    x_analytics_token: str = Header(...),
    settings: Settings = Depends(get_settings)
):
    if x_analytics_token != settings.analytics_api_token:
        raise HTTPException(status_code=403, detail="Invalid analytics token")
    return x_analytics_token


router = APIRouter(
    prefix="/analytics", 
    tags=["Analytics"],
    dependencies=[Depends(verify_analytics_token)]
)


async def query_posthog(
    query: Dict[str, Any],
    settings: Settings,
    redis: Redis,
    cache_key: str,
    cache_ttl: int = 300
) -> Dict[str, Any]:
    """
    Query PostHog Query API with caching.
    Uses POST /api/projects/{project_id}/query/ endpoint.
    
    Args:
        query: HogQL or Trends/Funnels query object
        settings: Application settings
        redis: Redis client for caching
        cache_key: Redis cache key
        cache_ttl: Cache TTL in seconds
    """
    if not settings.posthog_api_key or not settings.posthog_project_id:
        raise HTTPException(
            status_code=503,
            detail="PostHog integration not configured"
        )
    
    # Try cache first
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # Query PostHog
    url = f"{POSTHOG_API_BASE}/projects/{settings.posthog_project_id}/query/"
    headers = {
        "Authorization": f"Bearer {settings.posthog_api_key}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, headers=headers, json={"query": query})
            response.raise_for_status()
            data = response.json()
            
            # Cache the result
            await redis.setex(cache_key, cache_ttl, json.dumps(data))
            return data
        except httpx.HTTPError as e:
            raise HTTPException(
                status_code=502,
                detail=f"PostHog API error: {str(e)}"
            )


@router.get("/stats")
async def get_analytics_stats(
    request: Request,
    settings: Settings = Depends(get_settings),
    redis: Redis = Depends(get_redis)
) -> Dict[str, Any]:
    """
    Get KPI statistics for the analytics dashboard.
    
    Returns:
        - dau: Daily Active Users (last 24h)
        - quiz_completion_rate: Percentage who completed quiz
        - gift_ctr: Click-through rate on gift recommendations
        - total_sessions: Total quiz sessions started
    """
    try:
        # 1. Get DAU (Daily Active Users) using TrendsQuery
        dau_query = {
            "kind": "TrendsQuery",
            "series": [{"event": "page_viewed", "math": "dau"}],
            "dateRange": {"date_from": "-1d"}
        }
        dau_data = await query_posthog(
            dau_query,
            settings,
            redis,
            "analytics:dau:24h",
            cache_ttl=300
        )
        
        # Extract DAU value
        dau = 0
        results = dau_data.get("results", [])
        if results and len(results) > 0:
            latest = results[0].get("data", [])
            dau = int(latest[-1]) if latest else 0
        
        # 2. Get Quiz Funnel for completion rate using FunnelsQuery
        funnel_query = {
            "kind": "FunnelsQuery",
            "series": [
                {"event": "quiz_started"},
                {"event": "quiz_completed"}
            ],
            "dateRange": {"date_from": "-7d"}
        }
        funnel_data = await query_posthog(
            funnel_query,
            settings,
            redis,
            "analytics:quiz_funnel:7d",
            cache_ttl=600
        )
        
        # Calculate completion rate
        quiz_started = 0
        quiz_completed = 0
        completion_rate = 0.0
        
        results = funnel_data.get("results", [])
        if results and len(results) > 0:
            # Funnel results structure: [[step1_count, step2_count, ...]]
            steps = results[0] if isinstance(results[0], list) else results
            if len(steps) > 0:
                quiz_started = steps[0].get("count", 0) if isinstance(steps[0], dict) else steps[0]
            if len(steps) > 1:
                quiz_completed = steps[1].get("count", 0) if isinstance(steps[1], dict) else steps[1]
            
            if quiz_started > 0:
                completion_rate = round((quiz_completed / quiz_started) * 100, 2)
        
        # 3. Get Gift CTR using FunnelsQuery
        gift_funnel_query = {
            "kind": "FunnelsQuery",
            "series": [
                {"event": "results_shown"},
                {"event": "gift_clicked"}
            ],
            "dateRange": {"date_from": "-7d"}
        }
        gift_funnel_data = await query_posthog(
            gift_funnel_query,
            settings,
            redis,
            "analytics:gift_funnel:7d",
            cache_ttl=600
        )
        
        results_shown = 0
        gift_clicked = 0
        gift_ctr = 0.0
        
        results = gift_funnel_data.get("results", [])
        if results and len(results) > 0:
            steps = results[0] if isinstance(results[0], list) else results
            if len(steps) > 0:
                results_shown = steps[0].get("count", 0) if isinstance(steps[0], dict) else steps[0]
            if len(steps) > 1:
                gift_clicked = steps[1].get("count", 0) if isinstance(steps[1], dict) else steps[1]
            
            if results_shown > 0:
                gift_ctr = round((gift_clicked / results_shown) * 100, 2)
        
        return {
            "dau": dau,
            "quiz_completion_rate": completion_rate,
            "gift_ctr": gift_ctr,
            "total_sessions": quiz_started,
            "last_updated": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        # Return graceful fallback
        return {
            "dau": 0,
            "quiz_completion_rate": 0.0,
            "gift_ctr": 0.0,
            "total_sessions": 0,
            "last_updated": datetime.utcnow().isoformat(),
            "error": str(e)
        }


@router.get("/trends")
async def get_analytics_trends(
    request: Request,
    days: int = 7,
    settings: Settings = Depends(get_settings),
    redis: Redis = Depends(get_redis)
) -> Dict[str, Any]:
    """
    Get trend data for charts.
    
    Args:
        days: Number of days to fetch (default 7, max 90)
    
    Returns:
        - dates: List of dates
        - dau_trend: Daily active users by date
        - quiz_starts: Quiz starts by date
        - completion_rate_trend: Daily completion rate
    """
    if days > 90:
        days = 90
    
    try:
        # 1. Get DAU trend using TrendsQuery
        dau_query = {
            "kind": "TrendsQuery",
            "series": [{"event": "page_viewed", "math": "dau"}],
            "dateRange": {"date_from": f"-{days}d"},
            "interval": "day"
        }
        dau_data = await query_posthog(
            dau_query,
            settings,
            redis,
            f"analytics:dau_trend:{days}d",
            cache_ttl=600
        )
        
        dates = []
        dau_values = []
        
        results = dau_data.get("results", [])
        if results and len(results) > 0:
            result = results[0]
            dates = result.get("labels", [])
            dau_values = [int(v) for v in result.get("data", [])]
        
        # 2. Get quiz starts trend
        quiz_query = {
            "kind": "TrendsQuery",
            "series": [{"event": "quiz_started"}],
            "dateRange": {"date_from": f"-{days}d"},
            "interval": "day"
        }
        quiz_data = await query_posthog(
            quiz_query,
            settings,
            redis,
            f"analytics:quiz_trend:{days}d",
            cache_ttl=600
        )
        
        quiz_starts = []
        results = quiz_data.get("results", [])
        if results and len(results) > 0:
            quiz_starts = [int(v) for v in results[0].get("data", [])]
        
        return {
            "dates": dates,
            "dau_trend": dau_values,
            "quiz_starts": quiz_starts,
            "last_updated": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        return {
            "dates": [],
            "dau_trend": [],
            "quiz_starts": [],
            "last_updated": datetime.utcnow().isoformat(),
            "error": str(e)
        }


@router.get("/funnel")
async def get_conversion_funnel(
    request: Request,
    settings: Settings = Depends(get_settings),
    redis: Redis = Depends(get_redis)
) -> Dict[str, Any]:
    """
    Get full conversion funnel visualization data.
    
    Returns funnel steps with counts and conversion rates:
    quiz_started → quiz_completed → results_shown → gift_clicked
    """
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
            # FunnelsQuery returns structured step data
            for i, step_data in enumerate(results):
                if isinstance(step_data, dict):
                    steps.append({
                        "name": step_data.get("name", f"Step {i+1}"),
                        "count": step_data.get("count", 0),
                        "conversion_rate": round(step_data.get("conversionRates", {}).get("total", 0) * 100, 2)
                    })
        
        return {
            "steps": steps,
            "last_updated": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        return {
            "steps": [],
            "last_updated": datetime.utcnow().isoformat(),
            "error": str(e)
        }
@router.get("/technical")
async def get_technical_stats(
    request: Request,
    settings: Settings = Depends(get_settings),
    redis: Redis = Depends(get_redis)
) -> Dict[str, Any]:
    """
    Get technical health metrics from Prometheus and Loki.
    Used for the health-check section of the analytics dashboard.
    """
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
        # 1. Fetch from Prometheus
        try:
            # Query RPM (Requests per minute)
            # rate(http_requests_total[1m]) * 60
            prom_url = f"{settings.prometheus_url}/api/v1/query"
            
            # Simple health check from prom
            rpm_query = 'sum(rate(http_request_duration_seconds_count[5m])) * 60'
            resp = await client.get(prom_url, params={"query": rpm_query})
            if resp.status_code == 200:
                results = resp.json().get("data", {}).get("result", [])
                if results:
                    stats["requests_per_minute"] = round(float(results[0]["value"][1]), 2)
                    stats["api_health"] = "healthy"

            # Query Errors (5xx)
            err_query = 'sum(rate(http_request_duration_seconds_count{status=~"5.."}[5m]))'
            resp = await client.get(prom_url, params={"query": err_query})
            if resp.status_code == 200:
                results = resp.json().get("data", {}).get("result", [])
                if results:
                    stats["error_rate_5xx"] = round(float(results[0]["value"][1]), 4)

        except Exception as e:
            stats["api_health"] = f"error: {str(e)}"

        # 2. Fetch from Loki (Last 5 errors)
        try:
            loki_url = f"{settings.loki_url}/loki/api/v1/query_range"
            # Query for last 5 lines with 'error' or 'exception'
            loki_query = '{job=~".+"} |= "error" or "exception"'
            params = {
                "query": loki_query,
                "limit": 5,
                "direction": "backward"
            }
            resp = await client.get(loki_url, params=params)
            if resp.status_code == 200:
                results = resp.json().get("data", {}).get("result", [])
                logs = []
                for stream in results:
                    for val in stream.get("values", []):
                        # val is [timestamp_ns, log_line]
                        logs.append(val[1][:200] + "..." if len(val[1]) > 200 else val[1])
                stats["last_errors"] = logs[:5]
        except Exception:
            pass # Silently fail for Loki in this summary

    # Cache for 60 seconds
    await redis.setex(cache_key, 60, json.dumps(stats))
    return stats


from app.db import get_db
from app.repositories.parsing import ParsingRepository
from sqlalchemy import select, func
from app.models import CategoryMap, ParsingSource

@router.get("/scraping")
async def get_scraping_monitoring(
    request: Request,
    settings: Settings = Depends(get_settings),
    redis: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Detailed monitoring for the scraping system.
    Returns:
        - active_sources: Count of sources being scraped.
        - unmapped_categories: Number of categories needing AI classification.
        - scraped_items_24h: Total items scraped in last 24h (from Prometheus).
        - spider_status: Real-time status of each spider.
    """
    # 1. Database Stats
    repo = ParsingRepository(db)
    
    # Active sources count
    sources_stmt = select(func.count(ParsingSource.id)).where(ParsingSource.is_active == True)
    sources_count = (await db.execute(sources_stmt)).scalar() or 0
    
    # Unmapped categories
    unmapped_stmt = select(func.count(CategoryMap.id)).where(CategoryMap.internal_category_id == None)
    unmapped_count = (await db.execute(unmapped_stmt)).scalar() or 0
    
    # 2. Prometheus Metrics
    scraping_stats = {
        "active_sources": sources_count,
        "unmapped_categories": unmapped_count,
        "total_scraped_items": 0,
        "ingestion_errors": 0,
        "spiders": {}
    }
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            prom_url = f"{settings.prometheus_url}/api/v1/query"
            
            # 2.1 Total items scraped (sum across all spiders)
            items_query = 'sum(scraped_items_total)'
            resp = await client.get(prom_url, params={"query": items_query})
            if resp.status_code == 200:
                results = resp.json().get("data", {}).get("result", [])
                if results:
                    scraping_stats["total_scraped_items"] = int(float(results[0]["value"][1]))

            # 2.2 Ingestion errors
            errors_query = 'sum(ingestion_batches_total{status="error"})'
            resp = await client.get(prom_url, params={"query": errors_query})
            if resp.status_code == 200:
                results = resp.json().get("data", {}).get("result", [])
                if results:
                    scraping_stats["ingestion_errors"] = int(float(results[0]["value"][1]))

            # 2.3 Breakdown by spider
            spider_query = 'sum by (spider) (scraped_items_total)'
            resp = await client.get(prom_url, params={"query": spider_query})
            if resp.status_code == 200:
                for res in resp.json().get("data", {}).get("result", []):
                    spider_name = res["metric"]["spider"]
                    scraping_stats["spiders"][spider_name] = {
                        "items_scraped": int(float(res["value"][1]))
                    }

        except Exception as e:
            scraping_stats["error"] = f"Metric fetch error: {str(e)}"

    return scraping_stats
