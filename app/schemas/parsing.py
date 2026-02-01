from __future__ import annotations
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
    stats: dict[str, Any] = Field(default_factory=dict, description="Техническая статистика парсинга (время, ошибки)")
