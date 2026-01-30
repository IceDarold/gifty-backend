from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class GiftDTO(BaseModel):
    id: str = Field(..., description="Уникальный ID товара (например, site_key:url)")
    title: str = Field(..., description="Название товара")
    description: Optional[str] = Field(None, description="Описание товара")
    price: Optional[float] = Field(None, description="Цена в рублях")
    currency: Optional[str] = Field("RUB", description="Валюта")
    image_url: Optional[str] = Field(None, description="Ссылка на фото")
    product_url: str = Field(..., description="Прямая ссылка на магазин")
    merchant: Optional[str] = Field(None, description="Продавец")
    category: Optional[str] = Field(None, description="Внутренняя категория")

    model_config = {"from_attributes": True}


class Constraints(BaseModel):
    exclude_keywords: list[str] = Field(default_factory=list, description="Ключевые слова для исключения")
    exclude_categories: list[str] = Field(default_factory=list, description="ID или названия категорий для исключения")
    exclude_merchants: list[str] = Field(default_factory=list, description="Список магазинов-исключений")
    exclude_item_types: list[str] = Field(default_factory=list, description="Типы товаров (например, 'alcohol')")
    adult_allowed: bool = Field(False, description="Разрешить товары 18+")
    max_price: Optional[float] = Field(None, description="Максимальная цена")
    min_price: Optional[float] = Field(None, description="Минимальная цена")
    prefer_keywords: list[str] = Field(default_factory=list, description="Желаемые ключевые слова")
    avoid_keywords: list[str] = Field(default_factory=list, description="Нежелательные ключевые слова (с понижением веса)")
    prefer_categories: list[str] = Field(default_factory=list, description="Приоритетные категории")
    budget_strictness: Optional[str] = Field("soft", description="Строгость бюджета ('soft' или 'hard')")


class RecommendationRequest(BaseModel):
    recipient_age: int = Field(..., description="Возраст получателя")
    recipient_gender: Optional[str] = Field(None, description="Пол получателя ('male', 'female', 'neutral')")
    relationship: Optional[str] = Field(None, description="Отношения (друг, мама, коллега...)")
    occasion: Optional[str] = Field(None, description="Повод (день рождения, свадьба...)")
    vibe: Optional[str] = Field(None, description="Настроение подарка (прикольный, полезный, романтичный...)")
    interests: list[str] = Field(default_factory=list, description="Список интересов (ключевые слова)")
    interests_description: Optional[str] = Field(None, description="Произвольное описание интересов")
    budget: Optional[float] = Field(None, description="Целевой бюджет в рублях")
    city: Optional[str] = Field(None, description="Город доставки (для фильтрации магазинов)")
    top_n: int = Field(10, ge=1, le=30, description="Количество возвращаемых рекомендаций")
    constraints: Optional[Constraints] = Field(None, description="Дополнительные фильтры и ограничения")
    debug: bool = Field(False, description="Включить отладочную информацию в ответе")


class RecommendationResponse(BaseModel):
    quiz_run_id: str = Field(..., description="ID анкеты в базе данных")
    engine_version: str = Field(..., description="Версия алгоритма рекомендаций")
    featured_gift: GiftDTO = Field(..., description="Главная рекомендация (Hero Gift)")
    gifts: list[GiftDTO] = Field(..., description="Список остальных подходящих подарков")
    debug: Optional[dict[str, Any]] = Field(None, description="Отладочные данные поиска")


class ScoringTask(BaseModel):
    gift_id: str = Field(..., description="Внутренний ID товара")
    title: str = Field(..., description="Название для анализа")
    category: Optional[str] = Field(None, description="Категория")
    merchant: Optional[str] = Field(None, description="Продавец")
    price: Optional[float] = Field(None, description="Цена")
    image_url: Optional[str] = Field(None, description="Фото")
    content_text: Optional[str] = Field(None, description="Текст для анализа LLM")


class ScoringResult(BaseModel):
    gift_id: str = Field(..., description="ID товара")
    llm_gift_score: float = Field(..., description="Оценка от 0 до 10")
    llm_gift_reasoning: str = Field(..., description="Обоснование оценки от ИИ")
    llm_gift_vector: Optional[dict[str, Any]] = Field(None, description="Векторное описание подарка")
    llm_scoring_model: str = Field(..., description="Модель, проводившая скоринг")
    llm_scoring_version: str = Field(..., description="Версия промпта")


class ScoringBatchSubmit(BaseModel):
    results: list[ScoringResult] = Field(..., description="Список результатов скоринга для сохранения")
