from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class GiftDTO(BaseModel):
    id: str = Field(..., description="Unique product ID (e.g. takprodam:uuid)")
    title: str
    description: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = "RUB"
    image_url: Optional[str] = None
    product_url: str
    merchant: Optional[str] = None
    category: Optional[str] = None

    model_config = {"from_attributes": True}


class Constraints(BaseModel):
    exclude_keywords: list[str] = Field(default_factory=list)
    exclude_categories: list[str] = Field(default_factory=list)
    exclude_merchants: list[str] = Field(default_factory=list)
    exclude_item_types: list[str] = Field(default_factory=list)
    adult_allowed: bool = False
    max_price: Optional[float] = None
    min_price: Optional[float] = None
    prefer_keywords: list[str] = Field(default_factory=list)
    avoid_keywords: list[str] = Field(default_factory=list)
    prefer_categories: list[str] = Field(default_factory=list)
    budget_strictness: Optional[str] = "soft"


class RecommendationRequest(BaseModel):
    recipient_age: int
    recipient_gender: Optional[str] = None
    relationship: Optional[str] = None
    occasion: Optional[str] = None
    vibe: Optional[str] = None
    interests: list[str] = Field(default_factory=list)
    interests_description: Optional[str] = None
    budget: Optional[float] = None
    city: Optional[str] = None
    top_n: int = Field(10, ge=1, le=30)
    constraints: Optional[Constraints] = None
    debug: bool = False


class RecommendationResponse(BaseModel):
    quiz_run_id: str
    engine_version: str
    featured_gift: GiftDTO
    gifts: list[GiftDTO]
    debug: Optional[dict[str, Any]] = None


class ScoringTask(BaseModel):
    gift_id: str
    title: str
    category: Optional[str] = None
    merchant: Optional[str] = None
    price: Optional[float] = None


class ScoringResult(BaseModel):
    gift_id: str
    llm_gift_score: float
    llm_gift_reasoning: str
    llm_gift_vector: Optional[dict[str, Any]] = None
    llm_scoring_model: str
    llm_scoring_version: str


class ScoringBatchSubmit(BaseModel):
    results: list[ScoringResult]
