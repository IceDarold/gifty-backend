from fastapi import APIRouter, Depends, HTTPException, Header, Query, Body
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from typing import List, Optional, AsyncGenerator

from app.db import get_db, get_redis
from app.repositories.catalog import PostgresCatalogRepository
from app.schemas_v2 import ScoringTask, ScoringBatchSubmit
from app.config import get_settings

from app.config import get_settings
from app.utils.telegram_auth import verify_telegram_init_data
from app.repositories.parsing import ParsingRepository
from app.repositories.telegram import TelegramRepository

router = APIRouter(prefix="/api/v1/internal", tags=["internal"])
settings = get_settings()

async def verify_internal_token(
    x_internal_token: Optional[str] = Header(None),
    x_tg_init_data: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
):
    # 1. Direct system token check
    expected_token = getattr(settings, "internal_api_token", "default_secret_token")
    if x_internal_token:
        print(f"DEBUG_AUTH: Received token starts with {x_internal_token[:4]}, Expected starts with {expected_token[:4]}")
        if x_internal_token == expected_token:
            return x_internal_token
        else:
            print(f"DEBUG_AUTH: TOKEN MISMATCH!")
        
    # 2. Telegram WebApp session check
    if x_tg_init_data:
        # Dev bypass
        if settings.env == "dev" and x_tg_init_data == "dev_user_1821014162":
            user_id = 1821014162
        else:
            if not verify_telegram_init_data(x_tg_init_data, settings.telegram_bot_token):
                raise HTTPException(status_code=403, detail="Invalid Telegram data")
                
            from urllib.parse import parse_qsl
            import json
            params = dict(parse_qsl(x_tg_init_data))
            user_data = json.loads(params.get("user", "{}"))
            user_id = int(user_data.get("id", 0))

        if user_id:
            repo = TelegramRepository(db)
            subscriber = await repo.get_subscriber(user_id)
            if subscriber and subscriber.role in ["admin", "superadmin"]:
                return f"tg_admin:{user_id}"

    raise HTTPException(status_code=403, detail="Invalid internal token or unauthorized Telegram session")

@router.get("/scoring/tasks", response_model=List[ScoringTask], summary="Получить товары для скоринга")
async def get_scoring_tasks(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = PostgresCatalogRepository(db)
    products = await repo.get_products_without_llm_score(limit=limit)
    return [
        ScoringTask(
            gift_id=p.gift_id,
            title=p.title,
            category=p.category,
            merchant=p.merchant,
            price=float(p.price) if p.price is not None else None,
            image_url=p.image_url,
            content_text=p.content_text
        )
        for p in products
    ]

@router.post("/scoring/submit", summary="Сохранить результаты скоринга")
async def submit_scoring_results(
    batch: ScoringBatchSubmit,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = PostgresCatalogRepository(db)
    scores = [res.model_dump() for res in batch.results]
    count = await repo.save_llm_scores(scores)
    await db.commit()
    return {"status": "ok", "updated": count}

from app.schemas.parsing import IngestBatchRequest, ParsingSourceSchema, ParsingSourceCreate, DiscoveredCategorySchema
from app.services.ingestion import IngestionService

@router.get("/monitoring", summary="Агрегированный мониторинг по сайтам")
async def get_sites_monitoring(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db, redis=redis)
    return await repo.get_sites_monitoring()

@router.get("/stats", summary="Статистика парсинга за 24ч")
async def get_parsing_stats(
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db)
    return await repo.get_24h_stats()

@router.get("/sources", response_model=List[ParsingSourceSchema], summary="Получить список источников парсинга")
async def get_parsing_sources(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db, redis=redis)
    sources = await repo.get_all_sources()
    # Still keep full list for now, but in future this should be paginated
    return sources

@router.post("/sources", response_model=ParsingSourceSchema, summary="Создать или обновить источник парсинга")
async def upsert_parsing_source(
    data: ParsingSourceCreate,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db)
    return await repo.upsert_source(data.model_dump())

@router.post("/ingest-batch", summary="Прием партии товаров")
async def ingest_batch(
    request: IngestBatchRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    _ = Depends(verify_internal_token)
):
    service = IngestionService(db, redis=redis)
    
    p_count = 0
    if request.items:
        p_count = await service.ingest_products(request.items, request.source_id)
    
    c_count = 0
    if request.categories:
        c_count = await service.ingest_categories(request.categories)
        
    # Всегда логируем запуск, если есть source_id, чтобы видеть активность в дашборде
    if request.source_id:
        repo = ParsingRepository(db)
        
        # Если это был discovery (были категории, но не было товаров)
        if not request.items and c_count > 0:
            await repo.update_source_stats(request.source_id, {"status": "discovery_completed", "categories_found": c_count})
        
        if request.run_id:
            await repo.update_parsing_run(
                request.run_id,
                status="completed",
                items_scraped=len(request.items),
                items_new=p_count,
                error_message=None,
            )
        else:
            await repo.log_parsing_run(
                source_id=request.source_id,
                status="completed",
                items_scraped=len(request.items),
                items_new=p_count # В IngestionService.ingest_products возвращается число именно новых/обновленных
            )
        await db.commit()

    return {
        "status": "ok", 
        "items_ingested": p_count, 
        "categories_ingested": c_count
    }

@router.get("/workers", summary="Получить список активных воркеров")
async def get_active_workers(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db, redis=redis)
    return await repo.get_active_workers()

from app.schemas.parsing import ParsingErrorReport
from app.services.notifications import get_notification_service

@router.post("/sources/{source_id}/report-error", summary="Сообщить об ошибке парсера")
async def report_parsing_error(
    source_id: int,
    report: ParsingErrorReport,
    run_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db)
    source = await repo.report_source_error(source_id, report.error, report.is_broken)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    # Send notification via RabbitMQ
    notifier = get_notification_service()
    status_msg = "🚨 BROKEN" if report.is_broken else "⚠️ ERROR"
    text = (
        f"<b>{status_msg}: Parsing Source Failure</b>\n\n"
        f"<b>Site:</b> {source.site_key}\n"
        f"<b>URL:</b> {source.url}\n"
        f"<b>Error:</b> {report.error}"
    )
    await notifier.notify(topic="scraping", message=text, data={
        "source_id": source_id,
        "site_key": source.site_key,
        "is_broken": report.is_broken
    })

    if run_id:
        await repo.update_parsing_run(
            run_id,
            status="error",
            error_message=report.error,
        )
    
    return {"status": "ok"}
    
@router.post("/sources/{source_id}/force-run", summary="Принудительно запустить парсер")
async def force_run_parser(
    source_id: int,
    strategy: Optional[str] = None, # Allow override strategy (discovery vs deep)
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db)
    source = await repo.get_source_by_id(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
        
    # Queue the task manually
    from app.utils.rabbitmq import publish_parsing_task
    from datetime import datetime, timedelta
    
    run = await repo.create_parsing_run(source_id=source.id, status="queued")

    task = {
        "source_id": source.id,
        "run_id": run.id,
        "url": source.url,
        "site_key": source.site_key,
        "type": source.type,
        "strategy": strategy or source.strategy,
        "config": source.config
    }
    
    success = publish_parsing_task(task)
    if success:
        source.status = "running"
        source.next_sync_at = datetime.now() + timedelta(minutes=30)
        
        # Also update config for backward compatibility
        if source.config:
             cfg = dict(source.config)
             if source.config.get("last_stats"):
                 last_stats = dict(source.config["last_stats"])
                 last_stats["status"] = "queued_manual"
                 cfg["last_stats"] = last_stats
             source.config = cfg
             
        await db.commit()
        return {"status": "ok", "message": "Task queued for immediate execution"}
    else:
        await repo.update_parsing_run(
            run.id,
            status="error",
            error_message="Failed to publish task to RabbitMQ in force-run",
        )
        raise HTTPException(status_code=500, detail="Failed to publish task to queue")

@router.post("/sources/{source_id}/toggle", summary="Включить/выключить парсер")
async def toggle_parser(
    source_id: int,
    is_active: bool = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db)
    source = await repo.get_source_by_id(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
        
    await repo.set_source_active_status(source_id, is_active)
    if is_active:
        # Clear errors if re-enabling
        await repo.reset_source_error(source_id)
        
    return {"status": "ok", "is_active": is_active}

@router.post("/sources/{source_id}/report-status", summary="Обновить статус источника")
async def report_parsing_status(
    source_id: int,
    status: str = Body(..., embed=True),
    run_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db)
    await repo.set_source_status(source_id, status)
    if run_id:
        if status == "running":
            await repo.update_parsing_run(run_id, status="running")
        elif status == "waiting":
            await repo.update_parsing_run(run_id, status="completed")
    return {"status": "ok"}

@router.post("/sources/{source_id}/report-logs", summary="Обновить логи источника")
async def report_parsing_logs(
    source_id: int,
    logs: str = Body(..., embed=True),
    run_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db)
    trimmed_logs = logs[-100000:] if logs else logs
    await repo.update_source_logs(source_id, trimmed_logs)
    if run_id:
        await repo.update_parsing_run(run_id, logs=trimmed_logs)
    return {"status": "ok"}

@router.get("/sources/{source_id}", response_model=ParsingSourceSchema, summary="Получить детали источника")
async def get_parsing_source_details(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db)
    source = await repo.get_source_by_id(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    # Needs to match ParsingSourceSchema
    # Pydantic is smart enough to map attributes, but we need to inject the extra fields
    # Using jsonable_encoder or just dict conversion might be safer if we want to combine
    # But since we return the OBJECT and Pydantic validates it... we can assign attributes dynamically 
    # IF they are not in the ORM model. But Pydantic 'from_attributes=True' will try to read from ORM.
    # ORM model doesn't have these fields.
    # So we should construct the Schema object manually.
    
    
    # If it's a hub, aggregate stats and history for the whole site
    if source.type == "hub":
        total_items = await repo.get_total_products_count(source.site_key)
        status = await repo.get_aggregate_status(source.site_key)
        last_run_new = await repo.get_last_full_cycle_stats(source.site_key)
        history_raw = await repo.get_aggregate_history(source.site_key)
        aggregate_history_dicts = [
            {
                "date": h.day.isoformat(),
                "items_new": int(h.items_new or 0),
                "items_scraped": int(h.items_scraped or 0),
                "status": "completed"
            }
            for h in history_raw
        ]
        # Aggregate timestamps
        all_sources = await repo.get_all_sources()
        site_sources = [s for s in all_sources if s.site_key == source.site_key]
        last_synced = max([s.last_synced_at for s in site_sources if s.last_synced_at] or [None])
        next_sync = min([s.next_sync_at for s in site_sources] or [source.next_sync_at])
        history_dicts = []
    else:
        # It's a specific category/list
        # Total items specific to this category url
        # We assume gift_id is constructed as "site_key:product_url"
        # And product_url usually contains the category part or we can just count by what was scraped?
        # Actually parsing_runs has items_scraped, but total active items in DB?
        # We don't have a direct link from Product to Source ID. We only have gift_id.
        # But we know the source URL. GroupPrice products have /products/ ID. 
        # The relationship is weak.
        # However, for GroupPrice, we can try to filter by "category" field in Product table if we saved it?
        # We saved "category" in Product. Let's use that if possible.
        # But `upsert_products` saves `category` field.
        # Let's try to count by matching category name from source config?
        # Or just use the source URL as a filter if gift_id contains it? No.
        
        # Let's count by category name if available, otherwise 0 for now until we have better link.
        # config['discovery_name'] might match Product.category
        cat_name = source.config.get("discovery_name")
        if cat_name:
             total_items = await repo.get_total_category_products_count(source.site_key, cat_name)
        else:
             total_items = 0

        # Get detailed execution history instead of daily aggregates for the detail page
        history_raw = await repo.get_source_history(source_id, limit=20)
        history_dicts = [
            {
                "id": h.id,
                "source_id": h.source_id,
                "status": h.status,
                "items_scraped": h.items_scraped,
                "items_new": h.items_new,
                "error_message": h.error_message,
                "created_at": h.created_at
            }
            for h in history_raw
        ]
        
        last_run_new = history_raw[0].items_new if history_raw else 0
        
        status = source.status
        last_synced = source.last_synced_at
        next_sync = source.next_sync_at
        aggregate_history_dicts = []
 
    # Convert SQLAlchemy model to Pydantic compatible dict
    source_data = {c.name: getattr(source, c.name) for c in source.__table__.columns}
    source_data["status"] = status
    source_data["last_synced_at"] = last_synced
    source_data["next_sync_at"] = next_sync
    source_data["created_at"] = source.created_at
    source_data["total_items"] = total_items
    source_data["last_run_new"] = last_run_new
    source_data["history"] = history_dicts
    source_data["aggregate_history"] = aggregate_history_dicts
    
    return source_data

@router.get("/sources/{source_id}/products", summary="Получить товары источника")
async def get_source_products_endpoint(
    source_id: int,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    from app.repositories.parsing import ParsingRepository
    from app.repositories.catalog import PostgresCatalogRepository
    
    parsing_repo = ParsingRepository(db)
    source = await parsing_repo.get_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
        
    catalog_repo = PostgresCatalogRepository(db)
    
    # Filter by merchant (site_key)
    # If the source has a category name in config, we could filter by category too
    category_name = None
    if source.config:
        category_name = source.config.get("discovery_name")
        
    products = await catalog_repo.get_products(
        limit=limit,
        offset=offset,
        merchant=source.site_key,
        category=category_name
    )
    
    total = await catalog_repo.count_products(
        merchant=source.site_key,
        category=category_name
    )
    
    return {"items": products, "total": total}

from app.schemas.parsing import ParsingSourceUpdate

@router.patch("/sources/{source_id}", response_model=ParsingSourceSchema, summary="Обновить источник парсинга")
async def update_parsing_source_endpoint(
    source_id: int,
    data: ParsingSourceUpdate,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db)
    # Filter out None values to allow partial updates
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    source = await repo.update_source(source_id, update_data)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source

from app.schemas.parsing import SpiderSyncRequest

@router.post("/sources/sync-spiders", summary="Синхронизировать список пауков")
async def sync_spiders_endpoint(
    request: SpiderSyncRequest,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db)
    new_spiders = await repo.sync_spiders(request.available_spiders)
    
    if new_spiders:
        notifier = get_notification_service()
        spiders_str = ", ".join(new_spiders)
        text = (
            f"<b>🆕 New Spiders Detected</b>\n\n"
            f"The following spiders were found in the codebase but missing from the DB:\n"
            f"<code>{spiders_str}</code>\n\n"
            f"They have been added to the database as <b>inactive</b>. "
            f"Please configure their URLs and settings in the admin panel."
        )
        await notifier.notify(topic="scraping", message=text)
    
    return {"status": "ok", "new_spiders": new_spiders}

@router.get("/sources/backlog", response_model=List[DiscoveredCategorySchema], summary="Получить список discovery-категорий (бэклог)")
async def get_discovery_backlog(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db)
    return await repo.get_discovered_categories(limit=limit, states=["new"])

@router.post("/sources/backlog/activate", summary="Промоут категорий из discovery-бэклога в runtime sources")
async def activate_backlog_sources(
    payload: dict = Body(default={}),
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db)
    category_ids = payload.get("category_ids") or []
    legacy_source_ids = payload.get("source_ids") or []
    ids = category_ids or legacy_source_ids
    activated_count = await repo.activate_sources(ids)
    return {"status": "ok", "activated_count": activated_count}

@router.get("/sources/backlog/stats", summary="Статистика обнаружения за 24ч")
async def get_backlog_stats(
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db)
    promoted_today = await repo.count_promoted_categories_today()
    backlog_size = len(await repo.get_discovered_categories(limit=1000, states=["new"]))
    return {"promoted_today": promoted_today, "backlog_size": backlog_size}

@router.post("/sources/run-all", summary="Запустить все активные парсеры")
async def run_all_spiders_endpoint(
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db)
    sources = await repo.get_all_active_sources()
    from app.utils.rabbitmq import publish_parsing_task
    
    queued_count = 0
    failed_count = 0
    for source in sources:
        run = await repo.create_parsing_run(source_id=source.id, status="queued")
        task = {
            "source_id": source.id,
            "run_id": run.id,
            "url": source.url,
            "site_key": source.site_key,
            "type": source.type,
            "strategy": source.strategy,
            "config": source.config,
        }

        success = publish_parsing_task(task)
        if success:
            await repo.set_queued(source.id)
            queued_count += 1
        else:
            await repo.update_parsing_run(
                run.id,
                status="error",
                error_message="Failed to publish task to RabbitMQ in run-all",
            )
            failed_count += 1
        
    return {"status": "ok", "queued": queued_count, "failed": failed_count}

@router.delete("/sources/{source_id}/data", summary="Удалить все товары источника")
async def clear_source_data_endpoint(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    parsing_repo = ParsingRepository(db)
    source = await parsing_repo.get_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
        
    catalog_repo = PostgresCatalogRepository(db)
    # Products are linked to site_key, and gift_id prefix matches site_key
    count = await catalog_repo.delete_products_by_site(source.site_key)
    
    return {"status": "ok", "deleted": count}

@router.get("/sources/{source_id}/logs/stream", summary="Стрим логов паука в реальном времени")
async def stream_source_logs(
    source_id: int,
    redis: Redis = Depends(get_redis),
):
    """
    SSE endpoint returning logs for a specific source from Redis Pub/Sub.
    """
    async def log_generator() -> AsyncGenerator[str, None]:
        channel_name = f"logs:source:{source_id}"
        buffer_key = f"{channel_name}:buffer"
        
        # Send buffered logs first
        buffered_logs = await redis.lrange(buffer_key, 0, -1)
        for log in buffered_logs:
            yield f"data: {log}\n\n"

        pubsub = redis.pubsub()
        await pubsub.subscribe(channel_name)
        
        try:
            if not buffered_logs:
                # Send initial connection message only if there were no buffered logs
                yield "data: [CONNECTED] Real-time log stream started...\n\n"
            
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=10.0)
                if message and message['type'] == 'message':
                    data = message['data']
                    yield f"data: {data}\n\n"
                else:
                    yield "data: :ping\n\n"
        finally:
            await pubsub.unsubscribe(channel_name)
            await pubsub.close()

    return StreamingResponse(log_generator(), media_type="text/event-stream")

from app.schemas_v2 import CategoryMappingTask, CategoryBatchSubmit
from app.repositories.parsing import ParsingRepository

@router.get("/categories/tasks", response_model=List[CategoryMappingTask], summary="Получить категории для маппинга")
async def get_category_tasks(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db)
    categories = await repo.get_unmapped_categories(limit=limit)
    return [CategoryMappingTask(external_name=c.external_name) for c in categories]

@router.post("/categories/submit", summary="Сохранить результаты маппинга категорий")
async def submit_category_mappings(
    batch: CategoryBatchSubmit,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db)
    count = await repo.update_category_mappings([r.model_dump() for r in batch.results])
    return {"status": "ok", "updated": count}

from app.repositories.telegram import TelegramRepository
from pydantic import BaseModel
import hashlib

class SubscriberUpdate(BaseModel):
    chat_id: int
    name: Optional[str] = None
    slug: Optional[str] = None

def _hash_invite_password(password: str) -> str:
    secret = settings.secret_key or "change-me-in-production"
    raw = f"{secret}:{password}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class InviteCreate(BaseModel):
    username: str
    password: str
    name: Optional[str] = None
    mentor_id: Optional[int] = None
    permissions: Optional[List[str]] = None


class InviteClaim(BaseModel):
    username: str
    password: str
    chat_id: int
    name: Optional[str] = None
@router.get("/telegram/subscribers", summary="Получить список всех подписчиков")
async def list_telegram_subscribers(
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = TelegramRepository(db)
    return await repo.get_all_subscribers()

@router.get("/telegram/subscribers/{chat_id}")
async def get_telegram_subscriber(
    chat_id: int,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = TelegramRepository(db)
    sub = await repo.get_subscriber(chat_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    return sub

@router.get("/telegram/subscribers/by-username/{username}")
async def get_telegram_subscriber_by_username(
    username: str,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = TelegramRepository(db)
    slug = username.strip().lstrip("@").lower()
    sub = await repo.get_subscriber_by_slug(slug)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    return sub
@router.post("/telegram/subscribers")
async def create_telegram_subscriber(
    data: SubscriberUpdate,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = TelegramRepository(db)
    sub = await repo.create_subscriber(data.chat_id, data.name, data.slug)
    return sub

@router.post("/telegram/invites")
async def create_telegram_invite(
    data: InviteCreate,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = TelegramRepository(db)
    slug = data.username.strip().lstrip("@").lower()
    if not slug:
        raise HTTPException(status_code=400, detail="Invalid username")
    existing = await repo.get_subscriber_by_slug(slug)
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")
    if data.mentor_id is not None:
        mentor = await repo.get_subscriber_by_id(data.mentor_id)
        if not mentor:
            raise HTTPException(status_code=400, detail="Mentor not found")
    sub = await repo.create_invite(
        slug=slug,
        name=data.name,
        password_hash=_hash_invite_password(data.password),
        mentor_id=data.mentor_id,
        permissions=data.permissions or [],
    )
    return sub


@router.post("/telegram/invites/claim")
async def claim_telegram_invite(
    data: InviteClaim,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = TelegramRepository(db)
    slug = data.username.strip().lstrip("@").lower()
    sub = await repo.claim_invite(
        slug=slug,
        password_hash=_hash_invite_password(data.password),
        chat_id=data.chat_id,
        name=data.name,
    )
    if not sub:
        raise HTTPException(status_code=404, detail="Invite not found or password invalid")
    return sub
@router.post("/telegram/subscribers/{chat_id}/role")
async def set_subscriber_role(
    chat_id: int,
    role: str,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = TelegramRepository(db)
    success = await repo.set_role(chat_id, role)
    if not success:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    return {"status": "ok"}

@router.post("/telegram/subscribers/{chat_id}/permissions")
async def set_subscriber_permissions(
    chat_id: int,
    perms: List[str],
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = TelegramRepository(db)
    success = await repo.set_permissions(chat_id, perms)
    if not success:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    return {"status": "ok"}

@router.post("/telegram/subscribers/{chat_id}/subscribe")
async def subscribe_telegram_topic(
    chat_id: int,
    topic: str,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = TelegramRepository(db)
    success = await repo.subscribe_topic(chat_id, topic)
    return {"status": "ok" if success else "error"}

@router.post("/telegram/subscribers/{chat_id}/unsubscribe")
async def unsubscribe_telegram_topic(
    chat_id: int,
    topic: str,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = TelegramRepository(db)
    success = await repo.unsubscribe_topic(chat_id, topic)
    return {"status": "ok" if success else "error"}

@router.get("/telegram/topics/{topic}/subscribers")
async def get_topic_subscribers(
    topic: str,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = TelegramRepository(db)
    subscribers = await repo.get_subscribers_for_topic(topic)
    return subscribers

@router.post("/telegram/subscribers/{chat_id}/language")
async def set_telegram_language(
    chat_id: int,
    language: str = Query(...),
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = TelegramRepository(db)
    success = await repo.set_language(chat_id, language)
    return {"status": "ok" if success else "error"}
@router.post("/webapp/auth", summary="Авторизация через Telegram WebApp")
async def webapp_auth(
    init_data: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
):
    import logging
    logger = logging.getLogger("webapp_auth")
    logger.info(f"Webapp auth attempt. Init data length: {len(init_data)}")
    
    if not settings.telegram_bot_token:
        logger.error("Bot token not configured")
        raise HTTPException(status_code=500, detail="Bot token not configured")
        
    # Dev bypass
    if settings.env == "dev" and init_data == "dev_user_1821014162":
        logger.info("Using DEV BYPASS authentication for user 1821014162")
        user_id = 1821014162
    else:
        if not verify_telegram_init_data(init_data, settings.telegram_bot_token):
            logger.warning("Invalid init data verification failed")
            raise HTTPException(status_code=403, detail="Invalid init data")
            
        from urllib.parse import parse_qsl
        import json
        
        params = dict(parse_qsl(init_data))
        user_data = json.loads(params.get("user", "{}"))
        user_id = int(user_data.get("id", 0))
    
    logger.info(f"User ID from init_data: {user_id}")
    
    if not user_id:
        logger.warning("User ID not found in init data")
        raise HTTPException(status_code=400, detail="User ID not found in init data")
        
    repo = TelegramRepository(db)
    subscriber = await repo.get_subscriber(user_id)
    
    if not subscriber:
        logger.warning(f"Subscriber not found for {user_id}")
        
    if subscriber:
        logger.info(f"Subscriber found: {subscriber.chat_id}, Role: {subscriber.role}")

    if not subscriber or subscriber.role not in ["admin", "superadmin"]:
        logger.warning(f"Access denied for {user_id}. Role: {subscriber.role if subscriber else 'None'}")
        raise HTTPException(status_code=403, detail="Access denied")
        
    logger.info(f"Auth successful for {user_id}")
    return {
        "status": "ok",
        "user": {
            "id": subscriber.chat_id,
            "name": subscriber.name,
            "role": subscriber.role,
            "permissions": subscriber.permissions
        }
    }


@router.get("/products")
async def get_products_endpoint(
    limit: int = 50,
    offset: int = 0,
    is_active: Optional[bool] = None,
    merchant: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    from app.repositories.catalog import PostgresCatalogRepository
    repo = PostgresCatalogRepository(db)
    products = await repo.get_products(
        limit=limit, 
        offset=offset, 
        is_active=is_active, 
        merchant=merchant, 
        search=search
    )
    total = await repo.count_products(
        is_active=is_active, 
        merchant=merchant, 
        search=search
    )
    return {"items": products, "total": total}


@router.get("/queues/stats")
async def get_queue_stats(
    _ = Depends(verify_internal_token)
):
    import httpx
    import os
    
    # RabbitMQ Management API URL
    # guest:guest are default credentials for management plugin
    # In production should be changed to env variables
    rabbit_url = os.getenv("RABBITMQ_MANAGEMENT_URL", "http://guest:guest@rabbitmq:15672/api/queues/%2f/parsing_tasks")
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(rabbit_url)
            if resp.status_code != 200:
                return {"status": "error", "message": f"RabbitMQ API returned {resp.status_code}"}
            
            data = resp.json()
            return {
                "queue_name": data.get("name"),
                "messages_ready": data.get("messages_ready", 0),
                "messages_unacknowledged": data.get("messages_unacknowledged", 0), # currently running
                "messages_total": data.get("messages", 0),
                "consumers": data.get("consumers", 0),
                "rate_publish": data.get("messages_details", {}).get("rate", 0),
                "status": "ok"
            }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/queues/tasks")
async def get_queue_tasks(
    limit: int = 50,
    _=Depends(verify_internal_token)
):
    import httpx
    import os

    rabbit_url = os.getenv("RABBITMQ_MANAGEMENT_URL", "http://guest:guest@rabbitmq:15672/api/queues/%2f/parsing_tasks")
    rabbit_get_url = rabbit_url.rstrip("/") + "/get"

    payload = {
        "count": max(1, min(limit, 200)),
        "ackmode": "ack_requeue_true",
        "encoding": "auto",
        "truncate": 50000
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(rabbit_get_url, json=payload)
            if resp.status_code != 200:
                return {"status": "error", "message": f"RabbitMQ API returned {resp.status_code}", "items": []}

            raw_items = resp.json() if isinstance(resp.json(), list) else []
            items = []
            for i, msg in enumerate(raw_items):
                payload_data = msg.get("payload")
                parsed = payload_data if isinstance(payload_data, dict) else {}
                if not parsed and isinstance(payload_data, str):
                    try:
                        import json
                        parsed = json.loads(payload_data)
                    except Exception:
                        parsed = {"raw_payload": payload_data}

                items.append({
                    "idx": i,
                    "routing_key": msg.get("routing_key"),
                    "redelivered": msg.get("redelivered", False),
                    "exchange": msg.get("exchange"),
                    "payload_bytes": msg.get("payload_bytes"),
                    "properties": msg.get("properties", {}),
                    "task": parsed,
                })

            return {
                "status": "ok",
                "queue_name": "parsing_tasks",
                "count": len(items),
                "items": items
            }
    except Exception as e:
        return {"status": "error", "message": str(e), "items": []}


@router.get("/queues/history")
async def get_queue_history(
    limit: int = 100,
    _=Depends(verify_internal_token),
    db: AsyncSession = Depends(get_db),
):
    from datetime import timezone
    from sqlalchemy import select
    from app.models import ParsingRun, ParsingSource

    def calc_duration_seconds(run: ParsingRun) -> Optional[float]:
        if isinstance(run.duration_seconds, (int, float)):
            return float(run.duration_seconds)
        if run.status not in {"completed", "error"}:
            return None
        if run.created_at and run.updated_at:
            created_at = run.created_at
            updated_at = run.updated_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)
            duration = (updated_at - created_at).total_seconds()
            return max(duration, 0.0)
        return None

    stmt = (
        select(ParsingRun, ParsingSource)
        .join(ParsingSource, ParsingRun.source_id == ParsingSource.id)
        .where(ParsingRun.status.in_(("completed", "error")))
        .order_by(ParsingRun.created_at.desc())
        .limit(max(1, min(limit, 500)))
    )
    res = await db.execute(stmt)

    items = []
    for run, source in res.all():
        items.append({
            "id": run.id,
            "source_id": run.source_id,
            "site_key": source.site_key,
            "strategy": source.strategy,
            "status": run.status,
            "items_scraped": run.items_scraped,
            "items_new": run.items_new,
            "error_message": run.error_message,
            "duration_seconds": calc_duration_seconds(run),
            "created_at": run.created_at,
            "updated_at": run.updated_at,
            "logs_excerpt": (run.logs[-600:] if run.logs else None),
        })

    return {"status": "ok", "count": len(items), "items": items}


@router.get("/queues/history/{run_id}")
async def get_queue_history_run_details(
    run_id: int,
    _=Depends(verify_internal_token),
    db: AsyncSession = Depends(get_db),
):
    from datetime import timezone
    from sqlalchemy import select
    from app.models import ParsingRun, ParsingSource

    stmt = (
        select(ParsingRun, ParsingSource)
        .join(ParsingSource, ParsingRun.source_id == ParsingSource.id)
        .where(ParsingRun.id == run_id)
    )
    res = await db.execute(stmt)
    row = res.first()
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")

    run, source = row
    duration_seconds = run.duration_seconds
    if duration_seconds is None and run.status in {"completed", "error"} and run.created_at and run.updated_at:
        created_at = run.created_at
        updated_at = run.updated_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        duration_seconds = max((updated_at - created_at).total_seconds(), 0.0)

    return {
        "status": "ok",
        "item": {
            "id": run.id,
            "source_id": run.source_id,
            "site_key": source.site_key,
            "source_url": source.url,
            "strategy": source.strategy,
            "source_type": source.type,
            "run_status": run.status,
            "items_scraped": run.items_scraped,
            "items_new": run.items_new,
            "error_message": run.error_message,
            "duration_seconds": duration_seconds,
            "created_at": run.created_at,
            "updated_at": run.updated_at,
            "logs": run.logs or "",
        },
    }


@router.get("/analytics/intelligence", summary="AI Intelligence analytics summary")
async def get_intelligence_stats(
    days: int = 7,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    from sqlalchemy import select, func, and_, extract
    from app.models import LLMLog
    from datetime import datetime, timedelta, timezone
    from decimal import Decimal
    
    since = datetime.now(timezone.utc) - timedelta(days=days)
    
    # 1. Basic metrics
    stmt = select(
        func.count(LLMLog.id).label("total_requests"),
        func.sum(LLMLog.cost_usd).label("total_cost"),
        func.sum(LLMLog.total_tokens).label("total_tokens"),
        func.avg(LLMLog.latency_ms).label("avg_latency")
    ).where(LLMLog.created_at >= since)
    
    res = await db.execute(stmt)
    metrics = res.one()
    
    # 2. Provider distribution
    provider_stmt = select(
        LLMLog.provider,
        func.count(LLMLog.id).label("count"),
        func.sum(LLMLog.cost_usd).label("cost")
    ).where(LLMLog.created_at >= since).group_by(LLMLog.provider)
    
    providers_res = await db.execute(provider_stmt)
    providers = []
    for p in providers_res.all():
        cost_val = p.cost
        if isinstance(cost_val, Decimal):
            cost_val = float(cost_val)
        providers.append({
            "provider": p.provider, 
            "count": p.count, 
            "cost": cost_val or 0.0
        })
    
    # 3. Latency heatmap (by hour of day)
    latency_stmt = select(
        extract('hour', LLMLog.created_at).label("hour"),
        func.avg(LLMLog.latency_ms).label("avg_latency")
    ).where(LLMLog.created_at >= since).group_by("hour").order_by("hour")
    
    latency_res = await db.execute(latency_stmt)
    latency_data = []
    for l in latency_res.all():
        avg_lat = l.avg_latency
        if isinstance(avg_lat, Decimal):
            avg_lat = float(avg_lat)
        latency_data.append({
            "hour": int(l.hour), 
            "avg_latency": avg_lat or 0.0
        })
    
    # Prepare metrics with safe float conversion
    total_cost = metrics.total_cost
    if isinstance(total_cost, Decimal):
        total_cost = float(total_cost)
        
    avg_latency = metrics.avg_latency
    if isinstance(avg_latency, Decimal):
        avg_latency = float(avg_latency)
        
    return {
        "metrics": {
            "total_requests": metrics.total_requests or 0,
            "total_cost": total_cost or 0.0,
            "total_tokens": int(metrics.total_tokens or 0),
            "avg_latency": avg_latency or 0.0
        },
        "providers": providers,
        "latency_heatmap": latency_data
    }
@router.get("/health", summary="Detailed system health monitoring")
async def get_system_health(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    _ = Depends(verify_internal_token)
):
    import time
    from sqlalchemy import text
    
    start_time = time.time()
    
    # 1. DB Check
    db_healthy = False
    try:
        await db.execute(text("SELECT 1"))
        db_healthy = True
    except: pass
    
    # 2. Redis Check
    redis_healthy = False
    redis_info = {}
    try:
        await redis.ping()
        redis_healthy = True
        redis_info = await redis.info("memory")
    except: pass
    
    # 3. RabbitMQ Check (via management API if possible, or just skip if no URL)
    # Reusing logic from get_queue_stats but simpler
    
    latency_ms = int((time.time() - start_time) * 1000)
    
    return {
        "api": {
            "status": "Healthy",
            "latency": f"{latency_ms}ms",
            "uptime": "N/A" # Would need app start time tracking
        },
        "database": {
            "status": "Connected" if db_healthy else "ERROR",
            "engine": "PostgreSQL",
        },
        "redis": {
            "status": "Healthy" if redis_healthy else "ERROR",
            "memory_usage": f"{redis_info.get('used_memory_human', 'N/A')}",
        },
        "rabbitmq": {
            "status": "Healthy", # Placeholder, would need deeper check
        }
    }

from typing import AsyncGenerator
from fastapi.responses import StreamingResponse

@router.get("/sources/{source_id}/logs/stream", summary="Стрим логов паука в реальном времени")
async def get_source_log_stream(
    source_id: int,
    redis: Redis = Depends(get_redis),
):
    """
    SSE endpoint returning logs for a specific source from Redis Pub/Sub.
    """
    async def log_generator() -> AsyncGenerator[str, None]:
        channel_name = f"logs:source:{source_id}"
        buffer_key = f"{channel_name}:buffer"
        
        # Send buffered logs first
        buffered_logs = await redis.lrange(buffer_key, 0, -1)
        for log in buffered_logs:
            if isinstance(log, bytes):
                log = log.decode('utf-8')
            yield f"data: {log}\n\n"

        pubsub = redis.pubsub()
        await pubsub.subscribe(channel_name)
        
        try:
            if not buffered_logs:
                yield "data: [CONNECTED] Real-time log stream started...\n\n"
            
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=10.0)
                if message and message['type'] == 'message':
                    data = message['data']
                    if isinstance(data, bytes):
                        data = data.decode('utf-8')
                    yield f"data: {data}\n\n"
                else:
                    yield "data: :ping\n\n"
        finally:
            await pubsub.unsubscribe(channel_name)
            await pubsub.close()

    return StreamingResponse(log_generator(), media_type="text/event-stream")
