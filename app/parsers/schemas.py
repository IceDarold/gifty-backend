from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, Field

class ParsedProduct(BaseModel):
    title: str
    description: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = "RUB"
    image_url: Optional[str] = None
    product_url: str
    merchant: Optional[str] = None
    category: Optional[str] = None
    raw_data: Optional[dict[str, Any]] = None

    model_config = {"from_attributes": True}

class ParsedCatalog(BaseModel):
    products: list[ParsedProduct]
    source_url: str
    count: int
