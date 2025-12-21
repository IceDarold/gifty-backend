from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class GiftCandidate(BaseModel):
    gift_id: str
    title: str
    description: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    image_url: Optional[str] = None
    product_url: str
    merchant: Optional[str] = None
    category: Optional[str] = None
    raw: dict[str, Any]
