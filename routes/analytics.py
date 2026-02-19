from fastapi import APIRouter, HTTPException, Depends, Request, Header
from typing import Dict, Any, List
import httpx
from datetime import datetime, timedelta
from app.config import get_settings, Settings
from app.redis_client import get_redis
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
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
    prefix="/api/v1/analytics", 
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
        - quiz_completion_rate: % who completed quiz (last 7d)
        - gift_ctr: % click-through rate on recommendations (last 7d)
        - total_sessions: Total quiz sessions (last 7d)
        - last_updated: Timestamp
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
        
        quiz_started = 0
        quiz_completed = 0
        completion_rate = 0.0
        
        results = funnel_data.get("results", [])
        if results and len(results) > 0:
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
            "last_updated": datetime.utcnow().isoformat() + "Z"
        }
        
    except Exception:
        # Return graceful fallback
        return {
            "dau": 0,
            "quiz_completion_rate": 0.0,
            "gift_ctr": 0.0,
            "total_sessions": 0,
            "last_updated": datetime.utcnow().isoformat() + "Z"
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
            "last_updated": datetime.utcnow().isoformat() + "Z"
        }
        
    except Exception:
        return {
            "dates": [],
            "dau_trend": [],
            "quiz_starts": [],
            "last_updated": datetime.utcnow().isoformat() + "Z"
        }


@router.get("/funnel")
async def get_conversion_funnel(
    request: Request,
    settings: Settings = Depends(get_settings),
    redis: Redis = Depends(get_redis)
) -> Dict[str, Any]:
    """
    Get full conversion funnel visualization data.
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
        return {
            "steps": [],
            "last_updated": datetime.utcnow().isoformat() + "Z"
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
    
    async with httpx.AsyncClient(timeout=30.0) as client:
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

from app.models import SearchLog, Hypothesis as HypothesisModel, HypothesisProductLink

@router.get("/catalog/coverage")
async def get_catalog_coverage(
    days: int = 7,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Analyzes how well the catalog covers AI-generated search queries.
    """
    since = datetime.utcnow() - timedelta(days=days)
    
    # 1. Hit Rate & Quality Metrics
    stmt = select(
        func.count(SearchLog.id).label("total"),
        func.sum(case((SearchLog.results_count > 0, 1), else_=0)).label("hits"),
        func.avg(SearchLog.results_count).label("avg_results")
    ).where(SearchLog.created_at >= since)
    
    res = (await db.execute(stmt)).one_or_none()
    total = res.total if res else 0
    hits = res.hits if res else 0
    hit_rate = round((hits / total * 100), 2) if total > 0 else 0
    
    # 2. Top Zero-Result Queries (The "Catalog Gaps")
    gaps_stmt = (
        select(SearchLog.search_query, func.count(SearchLog.id).label("count"))
        .where(and_(SearchLog.created_at >= since, SearchLog.results_count == 0))
        .group_by(SearchLog.search_query)
        .order_by(func.count(SearchLog.id).desc())
        .limit(10)
    )
    gaps_res = await db.execute(gaps_stmt)
    top_gaps = [{"query": r.search_query, "misses": r.count} for r in gaps_res.all()]
    
    return {
        "period_days": days,
        "total_searches": total,
        "hit_rate": hit_rate,
        "avg_results_per_search": round(float(res.avg_results or 0), 2),
        "top_catalog_gaps": top_gaps,
        "last_updated": datetime.utcnow().isoformat() + "Z"
    }


@router.get("/catalog/hypotheses")
async def get_hypothesis_analytics(
    days: int = 30,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Analyzes user reactions to AI hypotheses.
    """
    since = datetime.utcnow() - timedelta(days=days)
    
    # 1. Global Sentiment
    stmt = select(
        func.count(HypothesisModel.id).label("total"),
        func.sum(case((HypothesisModel.user_reaction == 'like', 1), else_=0)).label("likes"),
        func.sum(case((HypothesisModel.user_reaction == 'dislike', 1), else_=0)).label("dislikes")
    ).where(and_(HypothesisModel.created_at >= since, HypothesisModel.is_shown == True))
    
    res = (await db.execute(stmt)).one_or_none()
    total = res.total if res else 0
    likes = res.likes if res else 0
    dislikes = res.dislikes if res else 0
    
    like_rate = round((likes / total * 100), 2) if total > 0 else 0
    dislike_rate = round((dislikes / total * 100), 2) if total > 0 else 0
    
    # 2. Performance by Track (Topic)
    track_stmt = (
        select(
            HypothesisModel.track_title,
            func.count(HypothesisModel.id).label("total"),
            func.sum(case((HypothesisModel.user_reaction == 'like', 1), else_=0)).label("likes")
        )
        .where(and_(HypothesisModel.created_at >= since, HypothesisModel.is_shown == True))
        .group_by(HypothesisModel.track_title)
        .order_by(func.sum(case((HypothesisModel.user_reaction == 'like', 1), else_=0)).desc())
        .limit(5)
    )
    track_res = await db.execute(track_stmt)
    top_tracks = [{
        "topic": r.track_title, 
        "total": r.total, 
        "likes": r.likes,
        "like_rate": round((r.likes / r.total * 100), 2) if r.total > 0 else 0
    } for r in track_res.all()]
    
@router.get("/catalog/coverage/trends")
async def get_coverage_trends(
    days: int = 14,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Returns time-series data for catalog coverage."""
    since = datetime.utcnow() - timedelta(days=days)
    
    # Group by date
    stmt = (
        select(
            func.date(SearchLog.created_at).label("date"),
            func.count(SearchLog.id).label("total"),
            func.sum(case((SearchLog.results_count > 0, 1), else_=0)).label("hits"),
            func.avg(SearchLog.results_count).label("avg_results")
        )
        .where(SearchLog.created_at >= since)
        .group_by(func.date(SearchLog.created_at))
        .order_by(func.date(SearchLog.created_at))
    )
    
    res = await db.execute(stmt)
    rows = res.all()
    
    return {
        "dates": [str(r.date) for r in rows],
        "hit_rate_trend": [round(float(r.hits or 0) / r.total * 100, 2) if r.total > 0 else 0 for r in rows],
        "avg_results_trend": [round(float(r.avg_results or 0), 2) for r in rows],
        "total_searches": [r.total for r in rows]
    }


@router.get("/catalog/coverage/segments")
async def get_coverage_segments(
    days: int = 7,
    group_by: str = "budget", # budget, model, track
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Analyzes coverage across different user segments."""
    since = datetime.utcnow() - timedelta(days=days)
    
    if group_by == "budget":
        # Group by budget buckets
        dim = case(
            (SearchLog.max_price < 1000, "0-1k"),
            (SearchLog.max_price < 3000, "1k-3k"),
            (SearchLog.max_price < 5000, "3k-5k"),
            else_="5k+"
        ).label("segment")
    elif group_by == "model":
        dim = SearchLog.llm_model.label("segment")
    else:
        dim = SearchLog.track_title.label("segment")

    stmt = (
        select(
            dim,
            func.count(SearchLog.id).label("total"),
            func.avg(case((SearchLog.results_count > 0, 100.0), else_=0.0)).label("hit_rate")
        )
        .where(SearchLog.created_at >= since)
        .group_by(dim)
        .order_by(func.count(SearchLog.id).desc())
    )
    
    res = await db.execute(stmt)
    return {
        "group_by": group_by,
        "segments": [{"name": str(r.segment or "unknown"), "total": r.total, "hit_rate": round(float(r.hit_rate or 0), 2)} for r in res.all()]
    }


@router.get("/catalog/hypotheses/funnel")
async def get_recommendation_funnel(
    days: int = 30,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Detailed funnel analysis of the recommendation loop."""
    since = datetime.utcnow() - timedelta(days=days)
    
    # 1. Total Hypotheses Generated
    total_stmt = select(func.count(HypothesisModel.id)).where(HypothesisModel.created_at >= since)
    total_count = (await db.execute(total_stmt)).scalar() or 0
    
    # 2. Shown to User
    shown_stmt = select(func.count(HypothesisModel.id)).where(and_(HypothesisModel.created_at >= since, HypothesisModel.is_shown == True))
    shown_count = (await db.execute(shown_stmt)).scalar() or 0
    
    # 3. Had Products (Coverage)
    # This is a join or subquery. Let's use SearchLog as proxy or just check if previews > 0
    # Actually, Hypothesis model doesn't store if it had products easily without a join.
    # Let's use the new HypothesisProductLink
    covered_stmt = select(func.count(func.distinct(HypothesisProductLink.hypothesis_id)))
    covered_count = (await db.execute(covered_stmt)).scalar() or 0
    
    # 4. Filtered Interest
    liked_stmt = select(func.count(HypothesisModel.id)).where(and_(HypothesisModel.created_at >= since, HypothesisModel.user_reaction == 'like'))
    liked_count = (await db.execute(liked_stmt)).scalar() or 0
    
    # 5. Product Clicks
    clicks_stmt = select(func.count(HypothesisProductLink.id)).where(HypothesisProductLink.was_clicked == True)
    clicks_count = (await db.execute(clicks_stmt)).scalar() or 0

    return {
        "period_days": days,
        "funnel": [
            {"stage": "1. Generated", "count": total_count, "pct": 100},
            {"stage": "2. Shown", "count": shown_count, "pct": round(shown_count/total_count*100, 1) if total_count > 0 else 0},
            {"stage": "3. Covered by Catalog", "count": covered_count, "pct": round(covered_count/shown_count*100, 1) if shown_count > 0 else 0},
            {"stage": "4. Liked/Interested", "count": liked_count, "pct": round(liked_count/shown_count*100, 1) if shown_count > 0 else 0},
            {"stage": "5. Product Clicks", "count": clicks_count, "pct": round(clicks_count/liked_count*100, 1) if liked_count > 0 else 0}
        ]
    }


@router.get("/catalog/coverage/drilldown")
async def get_coverage_drilldown(
    query: str,
    days: int = 30,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Provides detailed research data for a specific search query."""
    since = datetime.utcnow() - timedelta(days=days)
    
    stmt = (
        select(SearchLog)
        .where(and_(SearchLog.created_at >= since, SearchLog.search_query.ilike(f"%{query}%")))
        .order_by(SearchLog.created_at.desc())
        .limit(50)
    )
    
    res = await db.execute(stmt)
    logs = res.scalars().all()
    
    if not logs:
        return {"error": "No logs found for this query pattern"}

    total_searches = len(logs)
    avg_results = statistics.mean([l.results_count for l in logs])
    zero_results = len([l for l in logs if l.results_count == 0])
    
    return {
        "query_pattern": query,
        "total_searches": total_searches,
        "avg_results": round(avg_results, 1),
        "zero_result_rate": round(zero_results / total_searches * 100, 1),
        "related_hypotheses": list(set([l.hypothesis_title for l in logs if l.hypothesis_title])),
        "related_tracks": list(set([l.track_title for l in logs if l.track_title])),
        "recent_instances": [
            {
                "id": str(l.id),
                "created_at": l.created_at.isoformat(),
                "results": l.results_count,
                "model": l.llm_model,
                "max_price": l.max_price
            } for l in logs[:10]
        ]
    }


@router.get("/catalog/hypotheses/compare")
async def compare_analytics(
    period_a_days: int = 7,
    period_b_days: int = 7,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Compares two time periods (A/B) to measure performance improvements."""
    
    async def get_stats(days_offset: int, duration: int):
        end = datetime.utcnow() - timedelta(days=days_offset)
        start = end - timedelta(days=duration)
        
        # Hit Rate & Like Rate
        stmt = select(
            func.count(SearchLog.id).label("searches"),
            func.avg(case((SearchLog.results_count > 0, 100.0), else_=0.0)).label("hit_rate")
        ).where(and_(SearchLog.created_at >= start, SearchLog.created_at <= end))
        
        s_res = (await db.execute(stmt)).one_or_none()
        
        hypo_stmt = select(
            func.count(HypothesisModel.id).label("total"),
            func.avg(case((HypothesisModel.user_reaction == 'like', 100.0), else_=0.0)).label("like_rate")
        ).where(and_(HypothesisModel.created_at >= start, HypothesisModel.created_at <= end, HypothesisModel.is_shown == True))
        
        h_res = (await db.execute(hypo_stmt)).one_or_none()
        
        return {
            "hit_rate": round(float(s_res.hit_rate or 0), 2),
            "like_rate": round(float(h_res.like_rate or 0), 2),
            "total_searches": s_res.searches or 0,
            "total_hypotheses": h_res.total or 0
        }

    stats_b = await get_stats(0, period_b_days) # Recent
    stats_a = await get_stats(period_b_days, period_a_days) # Previous
    
    return {
        "period_a": stats_a,
        "period_b": stats_b,
        "delta": {
            "hit_rate": round(stats_b["hit_rate"] - stats_a["hit_rate"], 2),
            "like_rate": round(stats_b["like_rate"] - stats_a["like_rate"], 2)
        }
    }


@router.get("/catalog/hypotheses/details")
async def get_hypothesis_details(
    hypothesis_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Provides granular analytics for a specific AI hypothesis."""
    
    # Get the hypothesis metadata
    res = await db.execute(select(HypothesisModel).where(HypothesisModel.id == hypothesis_id))
    h = res.scalar_one_or_none()
    
    if not h:
        return {"error": "Hypothesis not found"}
        
    # Get shown products and their performance
    links_res = await db.execute(
        select(HypothesisProductLink)
        .where(HypothesisProductLink.hypothesis_id == hypothesis_id)
        .order_by(HypothesisProductLink.rank_position)
    )
    links = links_res.scalars().all()
    
    # Get search logs linked to this hypothesis
    logs_res = await db.execute(
        select(SearchLog).where(SearchLog.hypothesis_id == hypothesis_id)
    )
    logs = logs_res.scalars().all()
    
    return {
        "id": str(h.id),
        "title": h.title,
        "track": h.track_title,
        "reaction": h.user_reaction,
        "created_at": h.created_at.isoformat(),
        "search_efford": {
            "queries": [l.search_query for l in logs],
            "total_results_found": sum([l.results_count for l in logs])
        },
        "products": [
            {
                "gift_id": l.gift_id,
                "rank": l.rank_position,
                "score": l.similarity_score,
                "clicked": l.was_clicked
            } for l in links
        ]
    }


@router.get("/catalog/health")
async def get_system_health(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Composite health score for the recommendation system."""
    since = datetime.utcnow() - timedelta(days=3)
    
    # 1. Coverage Component
    cov_stmt = select(func.avg(case((SearchLog.results_count > 0, 100.0), else_=0.0))).where(SearchLog.created_at >= since)
    hit_rate = (await db.execute(cov_stmt)).scalar() or 0
    
    # 2. Relevance Component (Likes)
    rel_stmt = select(func.avg(case((HypothesisModel.user_reaction == 'like', 100.0), else_=0.0))).where(and_(HypothesisModel.created_at >= since, HypothesisModel.is_shown == True))
    like_rate = (await db.execute(rel_stmt)).scalar() or 0
    
    # 3. Perf Component (Slow searches)
    perf_stmt = select(func.avg(SearchLog.execution_time_ms)).where(SearchLog.created_at >= since)
    avg_perf = (await db.execute(perf_stmt)).scalar() or 0
    
    # Normalize to 0-100
    # Hit rate: 80% is 100 points
    cov_score = min(100, hit_rate / 0.8) if hit_rate > 0 else 0
    # Like rate: 25% is 100 points
    rel_score = min(100, like_rate / 0.25) if like_rate > 0 else 0
    
    overall = round((cov_score * 0.6 + rel_score * 0.4), 0)
    
    return {
        "health_score": overall,
        "components": {
            "catalog_coverage": {"score": round(cov_score, 0), "hit_rate": round(float(hit_rate), 1)},
            "recommendation_relevance": {"score": round(rel_score, 0), "like_rate": round(float(like_rate), 1)},
            "search_latency": {"avg_ms": round(float(avg_perf or 0), 0)}
        },
        "status": "healthy" if overall > 75 else "degraded" if overall > 50 else "critical"
    }
