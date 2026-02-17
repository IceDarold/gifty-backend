from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import sys
import pytest
import pytest_asyncio
from anthropic import APIConnectionError
from pathlib import Path as _Path

ROOT = _Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from app.config import get_settings
from app.services.ai_reasoning_service import AIReasoningService
from app.db import Base
from app.models import User, Recipient, Interaction, Hypothesis
from app.services.recipient_service import RecipientService
from .reporting import LLMReportWriter

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector


@compiles(UUID, "sqlite")
def _compile_uuid_sqlite(type_, compiler, **kw):
    return "CHAR(36)"


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "TEXT"


@compiles(Vector, "sqlite")
def _compile_vector_sqlite(type_, compiler, **kw):
    return "BLOB"


def _get_report_path() -> str:
    configured = os.getenv("LLM_REPORT_PATH")
    if configured:
        return configured
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    return str(Path("reports") / f"llm_quality_report_{ts}.md")


def _get_limit() -> Optional[int]:
    raw = os.getenv("LLM_TEST_LIMIT")
    if raw is None or raw == "":
        return 0
    try:
        return int(raw)
    except ValueError:
        return 0


@dataclass
class TimedResult:
    result: Any
    duration_s: float


class TimedAIReasoningService:
    def __init__(self, reporter: LLMReportWriter):
        self._service = AIReasoningService()
        self._reporter = reporter

    async def _time(self, name: str, coro, detail: Optional[str] = None):
        start = time.perf_counter()
        try:
            result = await coro
            duration = time.perf_counter() - start
            self._reporter.add_llm_call(name, duration, detail=detail)
            self._reporter.add_output(f"llm_raw:{name}", result)
            return result
        except (APIConnectionError, HttpxConnectError, OSError) as exc:
            duration = time.perf_counter() - start
            self._reporter.add_llm_call(name, duration, detail=f"connection error: {exc}")
            self._reporter.add_check(
                f"LLM call succeeded: {name}",
                "warn",
                detail="connection error",
            )
            self._reporter.add_note(f"Skipped due to LLM connection error in {name}: {exc}")
            pytest.skip("LLM connection error")

    async def normalize_topics(self, topics, language="ru"):
        return await self._time("normalize_topics", self._service.normalize_topics(topics, language=language))

    async def classify_topic(self, topic, quiz_data, language="ru"):
        return await self._time("classify_topic", self._service.classify_topic(topic, quiz_data, language=language))

    async def generate_hypotheses(self, topic, quiz_data, liked_concepts=None, disliked_concepts=None, shown_concepts=None, language="ru"):
        liked_concepts = liked_concepts or []
        disliked_concepts = disliked_concepts or []
        shown_concepts = shown_concepts or []
        return await self._time(
            "generate_hypotheses",
            self._service.generate_hypotheses(
                topic=topic,
                quiz_data=quiz_data,
                liked_concepts=liked_concepts,
                disliked_concepts=disliked_concepts,
                shown_concepts=shown_concepts,
                language=language,
            ),
        )

    async def generate_hypotheses_bulk(self, topics, quiz_data, liked_concepts=None, disliked_concepts=None, language="ru"):
        liked_concepts = liked_concepts or []
        disliked_concepts = disliked_concepts or []
        return await self._time(
            "generate_hypotheses_bulk",
            self._service.generate_hypotheses_bulk(
                topics=topics,
                quiz_data=quiz_data,
                liked_concepts=liked_concepts,
                disliked_concepts=disliked_concepts,
                language=language,
            ),
        )

    async def generate_personalized_probe(self, context_type, quiz_data, topic=None, language="ru"):
        return await self._time(
            f"generate_personalized_probe:{context_type}",
            self._service.generate_personalized_probe(
                context_type=context_type,
                quiz_data=quiz_data,
                topic=topic,
                language=language,
            ),
        )

    async def generate_topic_hints(self, quiz_data, topics_explored, language="ru"):
        return await self._time(
            "generate_topic_hints",
            self._service.generate_topic_hints(
                quiz_data=quiz_data,
                topics_explored=topics_explored,
                language=language,
            ),
        )


class InMemorySessionStorage:
    def __init__(self):
        self._sessions: Dict[str, Any] = {}

    async def save_session(self, session):
        self._sessions[session.session_id] = session

    async def get_session(self, session_id: str):
        return self._sessions.get(session_id)


@pytest.fixture(scope="session")
def llm_reporter():
    path = _get_report_path()
    writer = LLMReportWriter(path)
    yield writer
    writer.finalize()


@pytest.fixture(scope="session")
def llm_limit():
    return _get_limit()


@pytest.fixture(scope="session")
def llm_enabled():
    settings = get_settings()
    provider = settings.llm_provider.lower()
    
    key = None
    if provider == "anthropic":
        key = settings.anthropic_api_key
    elif provider == "gemini":
        key = settings.gemini_api_key
    elif provider == "groq":
        key = settings.groq_api_key
    elif provider == "openrouter":
        key = settings.openrouter_api_key
        
    if not key:
        pytest.skip(f"API key for {provider} not set; skipping LLM integration tests")
    return True


@pytest.fixture
def timed_ai_service(llm_reporter, llm_enabled):
    return TimedAIReasoningService(llm_reporter)


@pytest.fixture
def in_memory_session_storage():
    return InMemorySessionStorage()


@pytest_asyncio.fixture
async def sqlite_db_session(tmp_path):
    db_path = tmp_path / "llm_test.sqlite"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)

    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                User.__table__,
                Recipient.__table__,
                Interaction.__table__,
                Hypothesis.__table__,
            ],
        )

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def sqlite_recipient_service(sqlite_db_session):
    return RecipientService(sqlite_db_session)
