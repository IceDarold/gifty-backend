import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector

from app.db import Base
from app.models import ParsingSource, ParsingRun, CategoryMap, Product
from app.repositories.parsing import ParsingRepository
from app.jobs.parsing_scheduler import run_parsing_scheduler
from app.repositories.catalog import PostgresCatalogRepository

# --- SQLite Compiles for Postgres Dialects ---
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
    db_path = tmp_path / "scheduler_test.sqlite"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)

    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                ParsingSource.__table__,
                ParsingRun.__table__,
                CategoryMap.__table__,
                Product.__table__
            ],
        )

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        session.bind = engine
        yield session
    
    await engine.dispose()

@pytest.mark.asyncio
async def test_parsing_scheduler_flow(sqlite_db_session):
    repo = ParsingRepository(sqlite_db_session)
    
    # 1. Create a source that is "due" for sync (next_sync_at in the past)
    due_source = ParsingSource(
        site_key="test_site",
        url="https://test.com/due",
        type="list",
        strategy="deep",
        is_active=True,
        next_sync_at=datetime.utcnow() - timedelta(hours=1),
        status="waiting"
    )
    # 2. Create a source that is NOT due (next_sync_at in the future)
    future_source = ParsingSource(
        site_key="test_site",
        url="https://test.com/future",
        type="list",
        strategy="deep",
        is_active=True,
        next_sync_at=datetime.utcnow() + timedelta(hours=1),
        status="waiting"
    )
    sqlite_db_session.add_all([due_source, future_source])
    await sqlite_db_session.commit()

    # 3. Run the scheduler
    # We mock get_session_context to yield our sqlite session
    # We mock publish_parsing_task to capture what is sent to RabbitMQ
    mock_publish = MagicMock(return_value=True)
    
    with patch("app.jobs.parsing_scheduler.get_session_context") as mock_ctx:
        # Define an async context manager mock
        class AsyncContextManagerMock:
            async def __aenter__(self):
                return sqlite_db_session
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
        
        mock_ctx.return_value = AsyncContextManagerMock()
        
        with patch("app.jobs.parsing_scheduler.publish_parsing_task", mock_publish):
            await run_parsing_scheduler()

    # 4. Assertions
    # Check RabbitMQ publish call
    assert mock_publish.called
    assert mock_publish.call_count == 1
    task_sent = mock_publish.call_args[0][0]
    assert task_sent["url"] == "https://test.com/due"
    assert task_sent["site_key"] == "test_site"

    # Check database update
    # The "due" source should now be in 'queued' status
    await sqlite_db_session.refresh(due_source)
    assert due_source.status == "queued"
    
    # The "future" source should remain 'waiting'
    await sqlite_db_session.refresh(future_source)
    assert future_source.status == "waiting"

    print("\n✅ Parsing Scheduler flow (DB -> RabbitMQ) passed!")

@pytest.mark.asyncio
async def test_scraper_ingestion_with_stats(sqlite_db_session):
    from app.services.ingestion import IngestionService
    
    # Create a source
    source = ParsingSource(
        site_key="mrgeek",
        url="https://mrgeek.ru/cat",
        type="list",
        is_active=True,
        status="running"
    )
    sqlite_db_session.add(source)
    await sqlite_db_session.commit()
    await sqlite_db_session.refresh(source)

    service = IngestionService(sqlite_db_session)
    
    # Mock products and categories
    from app.schemas.parsing import ScrapedProduct, ScrapedCategory
    
    products = [
        ScrapedProduct(
            title="Cool Gift",
            product_url="https://mrgeek.ru/p1",
            price=100.0,
            site_key="mrgeek",
            merchant="mrgeek",
            category="Gifts"
        )
    ]
    
    categories = [
        ScrapedCategory(
            name="New Category",
            url="https://mrgeek.ru/new-cat",
            site_key="mrgeek"
        )
    ]

    # Ingest products
    # IngestionService.ingest_products callsParsingRepository.log_parsing_run and update_source_stats
    new_count = await service.ingest_products(products, source.id)
    assert new_count > 0

    # Verify run history (ParsingRun)
    from sqlalchemy import select
    runs_result = await sqlite_db_session.execute(select(ParsingRun))
    runs = runs_result.scalars().all()
    assert len(runs) == 1
    assert runs[0].items_scraped == 1
    assert runs[0].items_new == 1
    assert runs[0].status == "completed"

    print("✅ Ingestion flow with stats logging passed!")
