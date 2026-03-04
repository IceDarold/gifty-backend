from datetime import datetime
from typing import Any, Optional, List
from pydantic import BaseModel, Field

class ScrapedProduct(BaseModel):
    title: str = Field(..., description="Название товара")
    description: Optional[str] = Field(None, description="Полное описание товара (HTML или текст)")
    price: Optional[float] = Field(None, description="Цена товара в рублях")
    currency: Optional[str] = Field("RUB", description="Валюта цены")
    image_url: Optional[str] = Field(None, description="URL основного изображения")
    product_url: str = Field(..., description="Прямая ссылка на страницу товара")
    merchant: Optional[str] = Field(None, description="Название магазина (например, MrGeek)")
    category: Optional[str] = Field(None, description="Название категории на сайте-источнике")
    raw_data: Optional[dict[str, Any]] = Field(None, description="Оригинальные данные в формате JSON")
    site_key: str = Field(..., description="Краткий идентификатор сайта (например, 'mrgeek')")
    source_id: Optional[int] = Field(None, description="ID источника парсинга из базы данных")

class ScrapedCategory(BaseModel):
    name: str = Field(..., description="Название категории")
    url: str = Field(..., description="URL страницы категории")
    parent_url: Optional[str] = Field(None, description="URL родительской категории (если есть)")
    site_key: str = Field(..., description="Идентификатор сайта")

class IngestBatchRequest(BaseModel):
    items: List[ScrapedProduct] = Field(..., description="Список собранных товаров")
    categories: List[ScrapedCategory] = Field(default_factory=list, description="Список найденных категорий (для discovery)")
    source_id: int = Field(..., description="Идентификатор источника задачи")
    run_id: Optional[int] = Field(None, description="ID запуска в parsing_runs для обновления статуса")
    stats: dict[str, Any] = Field(default_factory=dict, description="Техническая статистика парсинга (время, ошибки)")

class ParsingRunSchema(BaseModel):
    id: int
    source_id: int
    status: str
    items_scraped: int
    items_new: int
    error_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class ParsingAggregateHistorySchema(BaseModel):
    date: datetime
    items_new: int
    items_scraped: int
    status: str = "completed"

class ParsingSourceSchema(BaseModel):
    id: int
    url: str
    type: str
    site_key: str
    strategy: str
    priority: int
    refresh_interval_hours: int
    last_synced_at: Optional[datetime] = None
    next_sync_at: datetime
    is_active: bool
    status: str
    config: Optional[dict[str, Any]] = None
    created_at: Optional[datetime] = None
    
    # Extra stats fields (filled manually by route)
    total_items: Optional[int] = Field(0, description="Total products in catalog")
    last_run_new: Optional[int] = Field(0, description="New items from last run")
    history: Optional[List[ParsingRunSchema]] = Field(None, description="Recent execution history")
    aggregate_history: Optional[List[ParsingAggregateHistorySchema]] = Field(None, description="Daily aggregate history for hub sources")
    related_sources: Optional[List[dict[str, Any]]] = Field(
        None,
        description="Related category/list sources for hub view, including discovered backlog categories",
    )

    class Config:
        from_attributes = True

class ParsingSourceCreate(BaseModel):
    url: str
    type: str
    site_key: str
    strategy: str = "deep"
    priority: int = 50
    refresh_interval_hours: int = 24
    is_active: bool = True
    config: Optional[dict[str, Any]] = None

class ParsingErrorReport(BaseModel):
    error: str
    is_broken: bool = True

class SpiderSyncRequest(BaseModel):
    available_spiders: List[str]

class ParsingSourceUpdate(BaseModel):
    url: Optional[str] = None
    type: Optional[str] = None
    strategy: Optional[str] = None
    priority: Optional[int] = None
    refresh_interval_hours: Optional[int] = None
    is_active: Optional[bool] = None
    config: Optional[dict[str, Any]] = None


class DiscoveredCategorySchema(BaseModel):
    id: int
    hub_id: Optional[int] = None
    site_key: str
    url: str
    name: Optional[str] = None
    parent_url: Optional[str] = None
    state: str
    promoted_source_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
