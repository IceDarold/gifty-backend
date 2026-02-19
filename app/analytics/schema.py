import strawberry
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json
import uuid
import httpx
import statistics
from strawberry.scalars import JSON
from sqlalchemy import select, func, and_, case
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Request

from app.config import Settings, get_settings
from app.redis_client import Redis
from app.models import SearchLog, Hypothesis as HypothesisModel, HypothesisProductLink, CategoryMap, ParsingSource
from app.repositories.parsing import ParsingRepository

# Use the same POSTHOG_API_BASE as in original file
POSTHOG_API_BASE = "https://app.posthog.com/api"

@strawberry.type
class KPIMetrics:
    dau: int
    quiz_completion_rate: float
    gift_ctr: float
    total_sessions: int
    last_updated: str

@strawberry.type
class TrendPoint:
    date: str
    value: float

@strawberry.type
class AnalyticsTrends:
    dates: List[str]
    dau_trend: List[int]
    quiz_starts: List[int]
    last_updated: str

@strawberry.type
class FunnelStep:
    name: str
    count: int
    conversion_rate: float

@strawberry.type
class CatalogGap:
    query: str
    misses: int

@strawberry.type
class CatalogCoverage:
    period_days: int
    total_searches: int
    hit_rate: float
    avg_results_per_search: float
    top_catalog_gaps: List[CatalogGap]
    last_updated: str

@strawberry.type
class ScrapingStats:
    active_sources: int
    unmapped_categories: int
    total_scraped_items: int
    ingestion_errors: int
    spiders: JSON

@strawberry.type
class TechnicalStats:
    api_health: str
    requests_per_minute: float
    error_rate_5xx: float
    last_errors: List[str]
    last_updated: str

@strawberry.type
class ComponentHealth:
    score: float
    hit_rate: Optional[float] = None
    like_rate: Optional[float] = None
    avg_ms: Optional[float] = None

@strawberry.type
class SystemHealth:
    health_score: float
    status: str
    catalog_coverage: ComponentHealth
    recommendation_relevance: ComponentHealth
    search_latency: ComponentHealth

@strawberry.type
class HypothesisDetails:
    id: strawberry.ID
    title: str
    track: str
    reaction: Optional[str]
    created_at: str
    search_queries: List[str]
    total_results_found: int
    products: JSON

async def query_posthog(query: Dict[str, Any], settings: Settings, redis: Redis, cache_key: str, cache_ttl: int = 300) -> Dict[str, Any]:
    if not settings.posthog_api_key or not settings.posthog_project_id:
        return {}
    
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)
    
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
            await redis.setex(cache_key, cache_ttl, json.dumps(data))
            return data
        except Exception:
            return {}

@strawberry.type
class Query:
    @strawberry.field
    async def stats(self, info: strawberry.Info) -> KPIMetrics:
        settings: Settings = info.context["settings"]
        redis: Redis = info.context["redis"]
        
        try:
            # 1. Get DAU
            dau_query = {
                "kind": "TrendsQuery",
                "series": [{"event": "page_viewed", "math": "dau"}],
                "dateRange": {"date_from": "-1d"}
            }
            dau_data = await query_posthog(dau_query, settings, redis, "analytics:dau:24h")
            dau = 0
            results = dau_data.get("results", [])
            if results and len(results) > 0:
                latest = results[0].get("data", [])
                dau = int(latest[-1]) if latest else 0

            # 2. Get Quiz Funnel
            funnel_query = {
                "kind": "FunnelsQuery",
                "series": [{"event": "quiz_started"}, {"event": "quiz_completed"}],
                "dateRange": {"date_from": "-7d"}
            }
            funnel_data = await query_posthog(funnel_query, settings, redis, "analytics:quiz_funnel:7d", cache_ttl=600)
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

            # 3. Get Gift CTR
            gift_funnel_query = {
                "kind": "FunnelsQuery",
                "series": [{"event": "results_shown"}, {"event": "gift_clicked"}],
                "dateRange": {"date_from": "-7d"}
            }
            gift_funnel_data = await query_posthog(gift_funnel_query, settings, redis, "analytics:gift_funnel:7d", cache_ttl=600)
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

            return KPIMetrics(
                dau=dau,
                quiz_completion_rate=completion_rate,
                gift_ctr=gift_ctr,
                total_sessions=quiz_started,
                last_updated=datetime.utcnow().isoformat() + "Z"
            )
        except Exception:
            return KPIMetrics(dau=0, quiz_completion_rate=0.0, gift_ctr=0.0, total_sessions=0, last_updated=datetime.utcnow().isoformat() + "Z")

    @strawberry.field
    async def trends(self, info: strawberry.Info, days: int = 7) -> AnalyticsTrends:
        settings: Settings = info.context["settings"]
        redis: Redis = info.context["redis"]
        if days > 90: days = 90
        
        try:
            dau_query = {
                "kind": "TrendsQuery",
                "series": [{"event": "page_viewed", "math": "dau"}],
                "dateRange": {"date_from": f"-{days}d"},
                "interval": "day"
            }
            dau_data = await query_posthog(dau_query, settings, redis, f"analytics:dau_trend:{days}d", cache_ttl=600)
            dates = []
            dau_values = []
            results = dau_data.get("results", [])
            if results and len(results) > 0:
                result = results[0]
                dates = result.get("labels", [])
                dau_values = [int(v) for v in result.get("data", [])]

            quiz_query = {
                "kind": "TrendsQuery",
                "series": [{"event": "quiz_started"}],
                "dateRange": {"date_from": f"-{days}d"},
                "interval": "day"
            }
            quiz_data = await query_posthog(quiz_query, settings, redis, f"analytics:quiz_trend:{days}d", cache_ttl=600)
            quiz_starts = []
            results = quiz_data.get("results", [])
            if results and len(results) > 0:
                quiz_starts = [int(v) for v in results[0].get("data", [])]

            return AnalyticsTrends(
                dates=dates,
                dau_trend=dau_values,
                quiz_starts=quiz_starts,
                last_updated=datetime.utcnow().isoformat() + "Z"
            )
        except Exception:
            return AnalyticsTrends(dates=[], dau_trend=[], quiz_starts=[], last_updated=datetime.utcnow().isoformat() + "Z")

    @strawberry.field
    async def funnel(self, info: strawberry.Info) -> List[FunnelStep]:
        settings: Settings = info.context["settings"]
        redis: Redis = info.context["redis"]
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
            funnel_data = await query_posthog(funnel_query, settings, redis, "analytics:full_funnel:30d", cache_ttl=600)
            steps = []
            results = funnel_data.get("results", [])
            if results:
                for i, step_data in enumerate(results):
                    if isinstance(step_data, dict):
                        steps.append(FunnelStep(
                            name=step_data.get("name", f"Step {i+1}"),
                            count=step_data.get("count", 0),
                            conversion_rate=round(step_data.get("conversionRates", {}).get("total", 0) * 100, 2)
                        ))
            return steps
        except Exception:
            return []

    @strawberry.field
    async def technical(self, info: strawberry.Info) -> TechnicalStats:
        settings: Settings = info.context["settings"]
        redis: Redis = info.context["redis"]
        cache_key = "analytics:technical_stats"
        cached = await redis.get(cache_key)
        if cached:
            data = json.loads(cached)
            return TechnicalStats(**data)

        stats = {
            "api_health": "unknown",
            "requests_per_minute": 0.0,
            "error_rate_5xx": 0.0,
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
                resp = await client.get(loki_url, params={"query": loki_query, "limit": 5, "direction": "backward"})
                if resp.status_code == 200:
                    results = resp.json().get("data", {}).get("result", [])
                    logs = []
                    for stream in results:
                        for val in stream.get("values", []):
                            logs.append(val[1][:200] + "..." if len(val[1]) > 200 else val[1])
                    stats["last_errors"] = logs[:5]
            except Exception:
                pass

        await redis.setex(cache_key, 60, json.dumps(stats))
        return TechnicalStats(**stats)

    @strawberry.field
    async def scraping(self, info: strawberry.Info) -> ScrapingStats:
        db: AsyncSession = info.context["db"]
        settings: Settings = info.context["settings"]
        
        sources_stmt = select(func.count(ParsingSource.id)).where(ParsingSource.is_active == True)
        sources_count = (await db.execute(sources_stmt)).scalar() or 0
        
        unmapped_stmt = select(func.count(CategoryMap.id)).where(CategoryMap.internal_category_id == None)
        unmapped_count = (await db.execute(unmapped_stmt)).scalar() or 0
        
        stats = {
            "active_sources": sources_count,
            "unmapped_categories": unmapped_count,
            "total_scraped_items": 0,
            "ingestion_errors": 0,
            "spiders": {}
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                prom_url = f"{settings.prometheus_url}/api/v1/query"
                items_query = 'sum(scraped_items_total)'
                resp = await client.get(prom_url, params={"query": items_query})
                if resp.status_code == 200:
                    results = resp.json().get("data", {}).get("result", [])
                    if results: stats["total_scraped_items"] = int(float(results[0]["value"][1]))

                errors_query = 'sum(ingestion_batches_total{status="error"})'
                resp = await client.get(prom_url, params={"query": errors_query})
                if resp.status_code == 200:
                    results = resp.json().get("data", {}).get("result", [])
                    if results: stats["ingestion_errors"] = int(float(results[0]["value"][1]))

                spider_query = 'sum by (spider) (scraped_items_total)'
                resp = await client.get(prom_url, params={"query": spider_query})
                if resp.status_code == 200:
                    for res in resp.json().get("data", {}).get("result", []):
                        spider_name = res["metric"]["spider"]
                        stats["spiders"][spider_name] = {"items_scraped": int(float(res["value"][1]))}
            except Exception:
                pass
        
        return ScrapingStats(**stats)

    @strawberry.field
    async def catalog_coverage(self, info: strawberry.Info, days: int = 7) -> CatalogCoverage:
        db: AsyncSession = info.context["db"]
        since = datetime.utcnow() - timedelta(days=days)
        
        stmt = select(
            func.count(SearchLog.id).label("total"),
            func.sum(case((SearchLog.results_count > 0, 1), else_=0)).label("hits"),
            func.avg(SearchLog.results_count).label("avg_results")
        ).where(SearchLog.created_at >= since)
        
        res = (await db.execute(stmt)).one_or_none()
        total = res.total if res else 0
        hits = res.hits if res else 0
        hit_rate = round((hits / total * 100), 2) if total > 0 else 0
        
        gaps_stmt = (
            select(SearchLog.search_query, func.count(SearchLog.id).label("count"))
            .where(and_(SearchLog.created_at >= since, SearchLog.results_count == 0))
            .group_by(SearchLog.search_query)
            .order_by(func.count(SearchLog.id).desc())
            .limit(10)
        )
        gaps_res = await db.execute(gaps_stmt)
        top_gaps = [CatalogGap(query=r.search_query, misses=r.count) for r in gaps_res.all()]
        
        return CatalogCoverage(
            period_days=days,
            total_searches=total,
            hit_rate=hit_rate,
            avg_results_per_search=round(float(res.avg_results or 0), 2),
            top_catalog_gaps=top_gaps,
            last_updated=datetime.utcnow().isoformat() + "Z"
        )

    @strawberry.field
    async def system_health(self, info: strawberry.Info) -> SystemHealth:
        db: AsyncSession = info.context["db"]
        since = datetime.utcnow() - timedelta(days=3)
        
        cov_stmt = select(func.avg(case((SearchLog.results_count > 0, 100.0), else_=0.0))).where(SearchLog.created_at >= since)
        hit_rate = (await db.execute(cov_stmt)).scalar() or 0
        
        rel_stmt = select(func.avg(case((HypothesisModel.user_reaction == 'like', 100.0), else_=0.0))).where(and_(HypothesisModel.created_at >= since, HypothesisModel.is_shown == True))
        like_rate = (await db.execute(rel_stmt)).scalar() or 0
        
        perf_stmt = select(func.avg(SearchLog.execution_time_ms)).where(SearchLog.created_at >= since)
        avg_perf = (await db.execute(perf_stmt)).scalar() or 0
        
        cov_score = min(100, hit_rate / 0.8) if hit_rate > 0 else 0
        rel_score = min(100, like_rate / 0.25) if like_rate > 0 else 0
        overall = round((cov_score * 0.6 + rel_score * 0.4), 0)
        
        return SystemHealth(
            health_score=overall,
            status="healthy" if overall > 75 else "degraded" if overall > 50 else "critical",
            catalog_coverage=ComponentHealth(score=round(cov_score, 0), hit_rate=round(float(hit_rate), 1)),
            recommendation_relevance=ComponentHealth(score=round(rel_score, 0), like_rate=round(float(like_rate), 1)),
            search_latency=ComponentHealth(score=0, avg_ms=round(float(avg_perf or 0), 0))
        )

    @strawberry.field
    async def hypothesis_details(self, info: strawberry.Info, id: uuid.UUID) -> Optional[HypothesisDetails]:
        db: AsyncSession = info.context["db"]
        res = await db.execute(select(HypothesisModel).where(HypothesisModel.id == id))
        h = res.scalar_one_or_none()
        if not h: return None
        
        links_res = await db.execute(select(HypothesisProductLink).where(HypothesisProductLink.hypothesis_id == id).order_by(HypothesisProductLink.rank_position))
        links = links_res.scalars().all()
        
        logs_res = await db.execute(select(SearchLog).where(SearchLog.hypothesis_id == id))
        logs = logs_res.scalars().all()
        
        return HypothesisDetails(
            id=strawberry.ID(str(h.id)),
            title=h.title,
            track=h.track_title,
            reaction=h.user_reaction,
            created_at=h.created_at.isoformat(),
            search_queries=[l.search_query for l in logs],
            total_results_found=sum([l.results_count for l in logs]),
            products=[{
                "gift_id": l.gift_id,
                "rank": l.rank_position,
                "score": l.similarity_score,
                "clicked": l.was_clicked
            } for l in links]
        )

schema = strawberry.Schema(query=Query)
