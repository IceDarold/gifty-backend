from __future__ import annotations

import uuid
from typing import Optional
from pydantic import BaseModel, EmailStr, HttpUrl, Field


class TeamMemberSchema(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    role: str
    bio: Optional[str] = None
    linkedin_url: Optional[str] = None
    photo_public_id: Optional[str] = None
    sort_order: int

    class Config:
        from_attributes = True


class InvestorContactCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    company: Optional[str] = Field(None, max_length=120)
    email: EmailStr
    linkedin: Optional[HttpUrl] = None
    hp: Optional[str] = None  # Honeypot field


class PartnerContactCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    company: Optional[str] = Field(None, max_length=120)
    website: Optional[HttpUrl] = None
    email: EmailStr
    message: str = Field(..., min_length=10, max_length=1000)
    hp: Optional[str] = None


class NewsletterSubscribe(BaseModel):
    email: EmailStr
    hp: Optional[str] = None
