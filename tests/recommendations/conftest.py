import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
import uuid
from typing import Dict, Any, List

@pytest.fixture
def mock_anthropic_service():
    mock = AsyncMock()
    mock.normalize_topics.return_value = ["Coffee", "Tech", "Books"]
    mock.classify_topic.return_value = {"is_wide": False, "refined_topic": "Specialty Coffee"}
    mock.generate_hypotheses.return_value = [
        {
            "title": "AeroPress Kit",
            "description": "Perfect for travel",
            "reasoning": "He likes coffee and travels",
            "primary_gap": "the_optimizer",
            "search_queries": ["aeropress kit", "travel coffee maker"]
        }
    ]
    mock.generate_hypotheses_bulk.return_value = {
        "Coffee": {
            "is_wide": False,
            "hypotheses": [
                {
                    "title": "Coffee Roasting Class",
                    "description": "Learn to roast",
                    "reasoning": "Deep dive into hobby",
                    "primary_gap": "permission_to_spend",
                    "search_queries": ["coffee roasting course"]
                }
            ]
        }
    }
    mock.generate_topic_hints.return_value = [
        {"text": "Does she like brewing at home?", "topic": "Home Brewing"}
    ]
    return mock

@pytest.fixture
def mock_intelligence_client():
    mock = AsyncMock()
    mock.get_embeddings.return_value = [[0.1] * 1536]
    mock.rerank.return_value = [0.95, 0.8, 0.7]
    return mock

@pytest.fixture
def mock_notification_service():
    mock = AsyncMock()
    mock.notify.return_value = True
    return mock

@pytest.fixture
def mock_session_storage():
    mock = AsyncMock()
    # Logic will use actual models mostly, but we mock the save/load
    return mock

@pytest.fixture
def mock_recipient_service():
    mock = AsyncMock()
    return mock

# --- Added for E2E Tests ---

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector
from app.db import Base
from app.models import User, Recipient, Interaction, Hypothesis

@compiles(UUID, "sqlite")
def _compile_uuid_sqlite(type_, compiler, **kw):
    return "CHAR(36)"

@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "TEXT"

@compiles(Vector, "sqlite")
def _compile_vector_sqlite(type_, compiler, **kw):
    return "BLOB"

@pytest_asyncio.fixture
async def sqlite_db_session(tmp_path):
    db_path = tmp_path / "e2e_test.sqlite"
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
def in_memory_session_storage():
    import json
    from recommendations.models import RecommendationSession
    
    class InMemorySessionStorage:
        def __init__(self):
            self._sessions = {}
        async def save_session(self, session):
            # Simulate Redis serialization
            self._sessions[session.session_id] = session.model_dump_json()
        async def get_session(self, session_id: str):
            data = self._sessions.get(session_id)
            if not data:
                return None
            return RecommendationSession.model_validate_json(data)
            
    return InMemorySessionStorage()
