from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional, List

import sqlalchemy as sa
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, Boolean, Float, Numeric
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.compiler import compiles
from pgvector.sqlalchemy import Vector

from app.db import Base

# Compatibility: Allow Postgres-specific types to be used with SQLite in tests
@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

@compiles(PG_UUID, "sqlite")
def compile_uuid_sqlite(type_, compiler, **kw):
    return "CHAR(32)"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class User(TimestampMixin, Base):
    """
    Модель пользователя системы Gifty.
    Хранит базовую информацию о пользователе и связи с OAuth аккаунтами.
    """
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    oauth_accounts: Mapped[list["OAuthAccount"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    # New relationship
    recipients: Mapped[list["Recipient"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class OAuthAccount(TimestampMixin, Base):
    """
    Связь пользователя с внешними провайдерами авторизации (Google, Yandex, VK).
    Хранит токены и идентификаторы провайдеров.
    """
    __tablename__ = "oauth_accounts"
    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_oauth_provider_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String, nullable=False)
    provider_user_id: Mapped[str] = mapped_column(String, nullable=False)
    email_at_provider: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    access_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="oauth_accounts")


class Recipient(TimestampMixin, Base):
    """
    Профиль человека, которому ищут подарок (Мама, Друг, Коллега).
    Связан с User (Giver).
    """
    __tablename__ = "recipients"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    
    # Basic Info
    name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    relation: Mapped[Optional[str]] = mapped_column(String, nullable=True) # friend, partner, etc.
    gender: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    age: Mapped[Optional[int]] = mapped_column(sa.Integer, nullable=True)
    birth_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Preferences / Context
    interests: Mapped[list[str]] = mapped_column(
        JSONB, server_default='[]', nullable=False
    )
    
    user: Mapped[Optional[User]] = relationship(back_populates="recipients")
    interactions: Mapped[list["Interaction"]] = relationship(
        back_populates="recipient", cascade="all, delete-orphan"
    )


class Interaction(TimestampMixin, Base):
    """
    История взаимодействия пользователя с рекомендациями для конкретного Recipient.
    """
    __tablename__ = "interactions"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("recipients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    
    action_type: Mapped[str] = mapped_column(String, nullable=False) # like, dislike, view, purchase
    target_type: Mapped[str] = mapped_column(String, nullable=False) # hypothesis, product
    target_id: Mapped[str] = mapped_column(String, nullable=False)
    
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True) # comment text or value
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    recipient: Mapped[Recipient] = relationship(back_populates="interactions")

class Hypothesis(TimestampMixin, Base):
    """
    Модель гипотезы (идеи подарка), сгенерированной ИИ.
    Позволяет анализировать эффективность идей и собирать фидбэк.
    """
    __tablename__ = "hypotheses"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    recipient_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("recipients.id", ondelete="CASCADE"), nullable=True, index=True
    )
    
    track_title: Mapped[str] = mapped_column(String, nullable=False) # Название топика (Кофе, Спорт)
    title: Mapped[str] = mapped_column(String, nullable=False)       # Название гипотезы
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)   # Обоснование ИИ
    search_queries: Mapped[list[str]] = mapped_column(
        JSONB, server_default='[]', nullable=False
    )
    
    # Feedback tracking
    user_reaction: Mapped[Optional[str]] = mapped_column(String, nullable=True) # like, dislike, shortlist
    is_shown: Mapped[bool] = mapped_column(sa.Boolean, server_default="true")
    
    # AI Metadata
    model_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    raw_response: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    recipient: Mapped[Optional[Recipient]] = relationship()


class Product(TimestampMixin, Base):
    """
    Основная модель товара в каталоге.
    Содержит метаданные товара, информацию о мерчанте и результаты оценки LLM.
    """
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
    raw: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, server_default="true", default=True, index=True)
    content_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # LLM Scoring
    llm_gift_score: Mapped[Optional[float]] = mapped_column(sa.Float, nullable=True, index=True)
    llm_gift_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    llm_gift_vector: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    llm_scoring_model: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    llm_scoring_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    llm_scored_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class ProductEmbedding(TimestampMixin, Base):
    """
    Векторные представления товаров для семантического поиска.
    Использует pgvector для хранения эмбеддингов.
    """
    __tablename__ = "product_embeddings"

    gift_id: Mapped[str] = mapped_column(Text, ForeignKey("products.gift_id", ondelete="CASCADE"), primary_key=True)
    model_name: Mapped[str] = mapped_column(Text, nullable=False, primary_key=True)
    model_version: Mapped[str] = mapped_column(Text, nullable=False, primary_key=True)
    dim: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1024), nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    embedded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ParsingSource(TimestampMixin, Base):
    """
    Реестр источников для парсинга (магазинов и категорий).
    Управляет расписанием и стратегией сбора данных.
    """
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
    is_active: Mapped[bool] = mapped_column(sa.Boolean, server_default="true", default=True, index=True)
    status: Mapped[str] = mapped_column(String, server_default="waiting", index=True) # waiting, running, error, broken
    config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)


class ParsingRun(TimestampMixin, Base):
    """
    История запусков парсеров.
    Хранит статистику по количеству спаршенных и новых товаров.
    """
    __tablename__ = "parsing_runs"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(sa.Integer, ForeignKey("parsing_sources.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String, nullable=False) # processing, completed, error
    items_scraped: Mapped[int] = mapped_column(sa.Integer, default=0)
    items_new: Mapped[int] = mapped_column(sa.Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(sa.Float, nullable=True)


class CategoryMap(TimestampMixin, Base):
    """
    Маппинг категорий внешних магазинов во внутренние категории Gifty.
    Используется для нормализации каталога.
    """
    __tablename__ = "category_maps"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    external_name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    internal_category_id: Mapped[Optional[int]] = mapped_column(sa.Integer, nullable=True)
    is_verified: Mapped[bool] = mapped_column(sa.Boolean, server_default="false")


class TeamMember(TimestampMixin, Base):
    __tablename__ = "team_members"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    linkedin_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    photo_public_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    sort_order: Mapped[int] = mapped_column(sa.Integer, server_default="0", default=0, index=True)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, server_default="true", default=True, index=True)


class InvestorContact(TimestampMixin, Base):
    __tablename__ = "investor_contacts"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    company: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    email: Mapped[str] = mapped_column(String, nullable=False, index=True)
    linkedin_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ip: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class PartnerContact(TimestampMixin, Base):
    __tablename__ = "partner_contacts"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    company: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    email: Mapped[str] = mapped_column(String, nullable=False, index=True)
    website_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    ip: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class TelegramSubscriber(TimestampMixin, Base):
    """
    Подписчики и администраторы Telegram бота.
    Управляет ролями, правами доступа и подписками на уведомления.
    """
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
        JSONB, server_default='[]', nullable=False
    )
    language: Mapped[str] = mapped_column(String, server_default="ru", nullable=False)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, server_default="true", default=True)
    role: Mapped[str] = mapped_column(String, server_default="user", nullable=False) # user, admin, superadmin
    permissions: Mapped[list[str]] = mapped_column(
        JSONB, server_default='[]', nullable=False
    )

class WeeekAccount(TimestampMixin, Base):
    """
    Связь аккаунта Telegram с сервисом Weeek.
    Хранит токены доступа и настройки для управления задачами.
    """
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
    
    is_active: Mapped[bool] = mapped_column(sa.Boolean, server_default="true", default=True)


class ComputeTask(TimestampMixin, Base):
    """
    Queue for offline compute tasks (embeddings, reranking, etc.).
    External workers (Kaggle, home clusters) poll this table via API.
    """
    __tablename__ = "compute_tasks"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_type: Mapped[str] = mapped_column(String, nullable=False, index=True)  # 'embedding', 'rerank'
    priority: Mapped[str] = mapped_column(String, server_default="low", index=True)  # 'low', 'high'
    status: Mapped[str] = mapped_column(String, server_default="pending", nullable=False, index=True)  # 'pending', 'processing', 'completed', 'failed'
    
    # Task data
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)  # Input data (texts, queries, etc.)
    result: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # Output data (vectors, scores, etc.)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Error message if failed
    
    # Worker tracking
    worker_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # ID of worker that picked up the task
    
    # Timing
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

class SearchLog(TimestampMixin, Base):
    """
    Логи поисковых запросов в системе рекомендаций.
    Позволяет анализировать полноту каталога и релевантность выдачи.
    """
    __tablename__ = "search_logs"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    hypothesis_id: Mapped[Optional[uuid.UUID]] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=True)
    
    # Context
    track_title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    hypothesis_title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    search_context: Mapped[Optional[str]] = mapped_column(String, nullable=True) # e.g. 'preview', 'deep_dive'
    llm_model: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    search_query: Mapped[str] = mapped_column(Text, nullable=False)
    results_count: Mapped[int] = mapped_column(Integer, default=0)
    predicted_category: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    
    # Metrics
    avg_similarity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    top_similarity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    top_gift_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # User state at search time
    max_price: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    execution_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Metadata
    engine_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class HypothesisProductLink(TimestampMixin, Base):
    """
    Связь конкретной гипотезы с найденными товарами.
    Нужна для анализа воронки "Гипотеза -> Найденные релевантные товары".
    """
    __tablename__ = "hypothesis_product_links"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hypothesis_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    gift_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    
    similarity_score: Mapped[float] = mapped_column(Float, nullable=False)
    rank_position: Mapped[int] = mapped_column(Integer, nullable=False) # Позиция в выдаче
    
    was_shown: Mapped[bool] = mapped_column(Boolean, default=True)
    was_clicked: Mapped[bool] = mapped_column(Boolean, default=False)


class LLMLog(TimestampMixin, Base):
    """
    Records every interaction with LLM providers for observability.
    Stores prompt, response, usage metrics and timing.
    """
    __tablename__ = "llm_logs"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String, nullable=False, index=True)
    model: Mapped[str] = mapped_column(String, nullable=False, index=True)
    
    # Context
    call_type: Mapped[str] = mapped_column(String, nullable=False, index=True)  # e.g., "generate_hypotheses", "classify_topic"
    
    # Input/Output
    input_messages: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    system_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Metrics
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Cost (estimated)
    cost_usd: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
    
    # Relations (optional links to product logic)
    session_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    hypothesis_id: Mapped[Optional[uuid.UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True, index=True)
    
    # A/B Testing
    experiment_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    variant_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
