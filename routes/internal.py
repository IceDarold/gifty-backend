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

@router.get("/scoring/tasks", response_model=List[ScoringTask])
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

@router.post("/scoring/submit")
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
