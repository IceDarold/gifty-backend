from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import Column, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.db import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    oauth_accounts: Mapped[list["OAuthAccount"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class OAuthAccount(TimestampMixin, Base):
    __tablename__ = "oauth_accounts"
    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_oauth_provider_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String, nullable=False)
    provider_user_id: Mapped[str] = mapped_column(String, nullable=False)
    email_at_provider: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    access_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="oauth_accounts")


class Product(TimestampMixin, Base):
    __tablename__ = "products"

    gift_id: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price: Mapped[Optional[float]] = mapped_column(sa.Numeric, nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    product_url: Mapped[str] = mapped_column(Text, nullable=False)
    merchant: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)
    category: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)
    raw: Mapped[Optional[dict]] = mapped_column(sa.dialects.postgresql.JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, server_default="true", index=True)
    content_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # LLM Scoring
    llm_gift_score: Mapped[Optional[float]] = mapped_column(sa.Float, nullable=True, index=True)
    llm_gift_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    llm_scoring_model: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    llm_scoring_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    llm_scored_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class ProductEmbedding(TimestampMixin, Base):
    __tablename__ = "product_embeddings"

    gift_id: Mapped[str] = mapped_column(Text, ForeignKey("products.gift_id", ondelete="CASCADE"), primary_key=True)
    model_name: Mapped[str] = mapped_column(Text, nullable=False, primary_key=True)
    model_version: Mapped[str] = mapped_column(Text, nullable=False, primary_key=True)
    dim: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1024), nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    embedded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
