from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class QuizAnswers(BaseModel):
    recipient_age: int
    relationship: Optional[str] = None
    occasion: Optional[str] = None
    vibe: Optional[str] = None
    interests: list[str] = []
    interests_description: Optional[str] = None
    budget: Optional[int] = None
