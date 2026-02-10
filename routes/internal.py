from fastapi import APIRouter, Depends, HTTPException, Header, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.db import get_db
from app.repositories.catalog import PostgresCatalogRepository
from app.schemas_v2 import ScoringTask, ScoringBatchSubmit
from app.config import get_settings

router = APIRouter(prefix="/internal", tags=["internal"])
settings = get_settings()

def verify_internal_token(x_internal_token: str = Header(...)):
    expected_token = getattr(settings, "internal_api_token", "default_secret_token")
    if x_internal_token != expected_token:
        raise HTTPException(status_code=403, detail="Invalid internal token")
    return x_internal_token

@router.get("/scoring/tasks", response_model=List[ScoringTask], summary="Получить товары для скоринга")
async def get_scoring_tasks(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    """
    Возвращает список товаров, которые еще не были оценены LLM моделями.
    Используется внешним воркером для формирования очереди на анализ.
    """
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
    """
    Принимает результаты анализа от LLM воркера.
    Обновляет оценки, обоснования и векторные представления товаров в БД.
    """
    repo = PostgresCatalogRepository(db)
    scores = [res.model_dump() for res in batch.results]
    count = await repo.save_llm_scores(scores)
    await db.commit()
    return {"status": "ok", "updated": count}

from app.schemas.parsing import IngestBatchRequest, ParsingSourceSchema, ParsingSourceCreate
from app.services.ingestion import IngestionService
from app.repositories.parsing import ParsingRepository

@router.get("/sources", response_model=List[ParsingSourceSchema], summary="Получить список источников парсинга")
async def get_parsing_sources(
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db)
    sources = await repo.get_all_sources()
    
    # We want to show aggregate status for hubs in the list view too
    # but we need to do it efficiently.
    # First, collect all statuses per site_key
    site_statuses = {}
    for s in sources:
        if s.site_key not in site_statuses:
            site_statuses[s.site_key] = []
        site_statuses[s.site_key].append(s.status)
        
    results = []
    for s in sources:
        source_data = {c.name: getattr(s, c.name) for c in s.__table__.columns}
        source_data["status"] = s.status
        
        # If it's a hub, use aggregate status
        if s.type == "hub":
            statuses = site_statuses.get(s.site_key, [])
            if "running" in statuses:
                source_data["status"] = "running"
            elif "error" in statuses:
                 source_data["status"] = "error"
            elif "broken" in statuses:
                 source_data["status"] = "broken"
                 
        results.append(source_data)
        
    return results

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
    _ = Depends(verify_internal_token)
):
    service = IngestionService(db)
    
    p_count = 0
    if request.items:
        p_count = await service.ingest_products(request.items, request.source_id)
    
    c_count = 0
    if request.categories:
        c_count = await service.ingest_categories(request.categories)
        
    # If it was a discovery task with NO products, we still need to record that it finished
    if not request.items and request.source_id:
        repo = ParsingRepository(db)
        await repo.update_source_stats(request.source_id, {"status": "discovery_completed", "categories_found": c_count})
        await repo.log_parsing_run(
            source_id=request.source_id,
            status="completed",
            items_scraped=0,
            items_new=0
        )
        await db.commit()

    return {
        "status": "ok", 
        "items_ingested": p_count, 
        "categories_ingested": c_count
    }

from app.schemas.parsing import ParsingErrorReport
from app.services.notifications import get_notification_service

@router.post("/sources/{source_id}/report-error", summary="Сообщить об ошибке парсера")
async def report_parsing_error(
    source_id: int,
    report: ParsingErrorReport,
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
    
    task = {
        "source_id": source.id,
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
        raise HTTPException(status_code=500, detail="Failed to publish task to queue")

@router.post("/sources/{source_id}/toggle", summary="Включить/выключить парсер")
async def toggle_parser(
    source_id: int,
    is_active: bool,
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
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db)
    await repo.set_source_status(source_id, status)
    return {"status": "ok"}

@router.post("/sources/{source_id}/report-logs", summary="Обновить логи источника")
async def report_parsing_logs(
    source_id: int,
    logs: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db)
    await repo.update_source_logs(source_id, logs)
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
    
    # If it's a hub, aggregate stats and history for the whole site
    if source.type == "hub":
        total_items = await repo.get_total_products_count(source.site_key)
        status = await repo.get_aggregate_status(source.site_key)
        last_run_new = await repo.get_last_full_cycle_stats(source.site_key)
        history_raw = await repo.get_aggregate_history(source.site_key)
        history_dicts = [
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
    else:
        # It's a specific category/list
        cat_name = source.config.get("discovery_name")
        if cat_name:
             total_items = await repo.get_total_category_products_count(source.site_key, cat_name)
        else:
             total_items = 0

        status = source.status
        history_raw = await repo.get_source_daily_history(source_id)
        history_dicts = [
            {
                "date": h.day.isoformat(),
                "items_new": int(h.items_new or 0),
                "items_scraped": int(h.items_scraped or 0),
                "status": "completed"
            }
            for h in history_raw
        ]
        
        detailed_history = await repo.get_source_history(source_id, limit=1)
        last_run_new = detailed_history[0].items_new if detailed_history else 0
        
        last_synced = source.last_synced_at
        next_sync = source.next_sync_at

    # Convert SQLAlchemy model to Pydantic compatible dict
    source_data = {c.name: getattr(source, c.name) for c in source.__table__.columns}
    source_data["status"] = status
    source_data["last_synced_at"] = last_synced
    source_data["next_sync_at"] = next_sync
    source_data["created_at"] = source.created_at
    source_data["total_items"] = total_items
    source_data["last_run_new"] = last_run_new
    source_data["history"] = history_dicts
    
    return source_data

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

# New Backlog endpoints
@router.get("/sources/backlog", response_model=List[ParsingSourceSchema], summary="Получить список обнаруженных источников (бэклог)")
async def get_discovery_backlog(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db)
    return await repo.get_discovered_sources(limit=limit)

@router.post("/sources/backlog/activate", summary="Массовая активация источников из бэклога")
async def activate_backlog_sources(
    source_ids: List[int] = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db)
    await repo.activate_sources(source_ids)
    return {"status": "ok", "activated_count": len(source_ids)}

@router.get("/sources/backlog/stats", summary="Статистика обнаружения за 24ч")
async def get_backlog_stats(
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    repo = ParsingRepository(db)
    count = await repo.count_discovered_today()
    return {"discovered_today": count}


from app.schemas_v2 import CategoryMappingTask, CategoryBatchSubmit

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
