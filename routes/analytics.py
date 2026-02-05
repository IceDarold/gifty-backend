from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Dict, Any, List
import httpx
from datetime import datetime, timedelta
from app.config import get_settings, Settings
from app.redis_client import get_redis
from redis.asyncio import Redis
import json

router = APIRouter(prefix="/analytics", tags=["Analytics"])

POSTHOG_API_BASE = "https://app.posthog.com/api"


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
