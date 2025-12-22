from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class QuizAnswers(BaseModel):
    recipient_age: int
    recipient_gender: Optional[str] = None
    relationship: Optional[str] = None
    occasion: Optional[str] = None
    vibe: Optional[str] = None
    interests: list[str] = []
    interests_description: Optional[str] = None
    budget: Optional[int] = None


class GiftDTO(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    image_url: Optional[str] = None
    product_url: str
    merchant: Optional[str] = None
    category: Optional[str] = None
    budget: Optional[int] = None
