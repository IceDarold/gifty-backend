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
    llm_gift_vector: Mapped[Optional[dict]] = mapped_column(sa.dialects.postgresql.JSONB, nullable=True)
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


class ParsingSource(TimestampMixin, Base):
    __tablename__ = "parsing_sources"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    type: Mapped[str] = mapped_column(String, nullable=False)  # hub, list, product, sitemap
    site_key: Mapped[str] = mapped_column(String, nullable=False, index=True)  # mrgeek, ozon, etc.
    strategy: Mapped[str] = mapped_column(String, server_default="deep")  # deep, discovery
    priority: Mapped[int] = mapped_column(sa.Integer, server_default="50", index=True)
    refresh_interval_hours: Mapped[int] = mapped_column(sa.Integer, server_default="24")
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_sync_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, server_default="true", index=True)
    status: Mapped[str] = mapped_column(String, server_default="waiting", index=True) # waiting, running, error, broken
    config: Mapped[Optional[dict]] = mapped_column(sa.dialects.postgresql.JSONB, nullable=True)


class ParsingRun(TimestampMixin, Base):
    __tablename__ = "parsing_runs"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(sa.Integer, ForeignKey("parsing_sources.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String, nullable=False) # processing, completed, error
    items_scraped: Mapped[int] = mapped_column(sa.Integer, default=0)
    items_new: Mapped[int] = mapped_column(sa.Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(sa.Float, nullable=True)


class CategoryMap(TimestampMixin, Base):
    __tablename__ = "category_maps"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    external_name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    internal_category_id: Mapped[Optional[int]] = mapped_column(sa.Integer, nullable=True)
    is_verified: Mapped[bool] = mapped_column(sa.Boolean, server_default="false")


class TeamMember(TimestampMixin, Base):
    __tablename__ = "team_members"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    linkedin_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    photo_public_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    sort_order: Mapped[int] = mapped_column(sa.Integer, server_default="0", index=True)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, server_default="true", index=True)


class InvestorContact(TimestampMixin, Base):
    __tablename__ = "investor_contacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    company: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    email: Mapped[str] = mapped_column(String, nullable=False, index=True)
    linkedin_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ip: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class TelegramSubscriber(TimestampMixin, Base):
    __tablename__ = "telegram_subscribers"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[Optional[int]] = mapped_column(sa.BigInteger, unique=True, nullable=True, index=True)
    slug: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # TG Username or similar
    name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    invite_password_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mentor_id: Mapped[Optional[int]] = mapped_column(
        sa.Integer, ForeignKey("telegram_subscribers.id", ondelete="SET NULL"), nullable=True
    )
    subscriptions: Mapped[list[str]] = mapped_column(
        sa.dialects.postgresql.JSONB, server_default='[]', nullable=False
    )
    language: Mapped[str] = mapped_column(String, server_default="ru", nullable=False)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, server_default="true")
    role: Mapped[str] = mapped_column(String, server_default="user", nullable=False) # user, admin, superadmin
    permissions: Mapped[list[str]] = mapped_column(
        sa.dialects.postgresql.JSONB, server_default='[]', nullable=False
    )

class WeeekAccount(TimestampMixin, Base):
    __tablename__ = "weeek_accounts"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    telegram_chat_id: Mapped[int] = mapped_column(sa.BigInteger, ForeignKey("telegram_subscribers.chat_id"), unique=True, index=True)
    
    # Weeek credentials
    weeek_api_token: Mapped[str] = mapped_column(String, nullable=False)  # Encrypted!
    weeek_user_id: Mapped[str] = mapped_column(String, nullable=True)    # ID пользователя в Weeek
    weeek_workspace_id: Mapped[Optional[int]] = mapped_column(sa.Integer, nullable=True)
    
    # Personal project setup
    personal_project_id: Mapped[Optional[int]] = mapped_column(sa.Integer, nullable=True)  # Проект "Gifty" у юзера
    personal_board_id: Mapped[Optional[int]] = mapped_column(sa.Integer, nullable=True)    # Основная доска
    
    # Preferences
    reminder_time: Mapped[str] = mapped_column(String, server_default="09:00")  # Время напоминаний
    timezone: Mapped[str] = mapped_column(String, server_default="Europe/Moscow")
    
    is_active: Mapped[bool] = mapped_column(sa.Boolean, server_default="true")
