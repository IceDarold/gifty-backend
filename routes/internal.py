from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.db import get_db
from app.repositories.catalog import PostgresCatalogRepository
from app.schemas_v2 import ScoringTask, ScoringBatchSubmit
from app.config import get_settings

router = APIRouter(prefix="/internal", tags=["internal"])
settings = get_settings()

def verify_internal_token(x_internal_token: str = Header(...)):
    # In a real app, this should be in settings/env
    # For now, we'll use a placeholder or check settings if it's there
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

from app.schemas.parsing import IngestBatchRequest
from app.services.ingestion import IngestionService

@router.post("/ingest-batch", summary="Прием партии товаров")
async def ingest_batch(
    request: IngestBatchRequest,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    """
    Основной эндпоинт для загрузки данных из парсеров.
    
    **Процесс:**
    1. Принимает список товаров и метаданные источника.
    2. Проверяет новые категории и создает записи в `category_maps`.
    3. Выполняет `bulk upsert` товаров в базу данных.
    4. Обновляет статистику источника.
    """
    service = IngestionService(db)
    count = await service.ingest_products(request.items, request.source_id)
    return {"status": "ok", "items_ingested": count}

from app.schemas_v2 import CategoryMappingTask, CategoryBatchSubmit
from app.repositories.parsing import ParsingRepository

@router.get("/categories/tasks", response_model=List[CategoryMappingTask], summary="Получить категории для маппинга")
async def get_category_tasks(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    """
    Возвращает внешние категории, которые еще не привязаны к внутренней структуре Gifty.
    Используется AI воркером для классификации.
    """
    repo = ParsingRepository(db)
    categories = await repo.get_unmapped_categories(limit=limit)
    return [CategoryMappingTask(external_name=c.external_name) for c in categories]

@router.post("/categories/submit", summary="Сохранить результаты маппинга категорий")
async def submit_category_mappings(
    batch: CategoryBatchSubmit,
    db: AsyncSession = Depends(get_db),
    _ = Depends(verify_internal_token)
):
    """
    Принимает от AI воркера привязки внешних категорий к внутренним.
    """
    repo = ParsingRepository(db)
    count = await repo.update_category_mappings([r.model_dump() for r in batch.results])
    return {"status": "ok", "updated": count}
