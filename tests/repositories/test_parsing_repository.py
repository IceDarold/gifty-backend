
import pytest
import datetime
from unittest.mock import AsyncMock
from sqlalchemy import text
from app.repositories.parsing import ParsingRepository
from app.models import ParsingSource, CategoryMap

@pytest.mark.asyncio
async def test_get_due_sources(postgres_session):
    repo = ParsingRepository(postgres_session)
    
    # Create test sources
    source1 = ParsingSource(
        site_key="active_due",
        url="http://example.com/1",
        type="rss",
        strategy="simple",
        is_active=True,
        next_sync_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1),
        priority=10
    )
    source2 = ParsingSource(
        site_key="inactive",
        url="http://example.com/2",
        type="rss",
        strategy="simple",
        is_active=False,
        next_sync_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1),
        priority=5
    )
    source3 = ParsingSource(
        site_key="active_future",
        url="http://example.com/3",
        type="rss",
        strategy="simple",
        is_active=True,
        next_sync_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1),
        priority=5
    )
    
    postgres_session.add_all([source1, source2, source3])
    await postgres_session.commit()
    
    due = await repo.get_due_sources()
    assert len(due) == 1
    assert due[0].site_key == "active_due"

@pytest.mark.asyncio
async def test_update_source_stats(postgres_session):
    repo = ParsingRepository(postgres_session)
    
    source = ParsingSource(
        site_key="stats_test",
        url="http://example.com/stats",
        type="rss",
        strategy="simple",
        is_active=True,
        refresh_interval_hours=2
    )
    postgres_session.add(source)
    await postgres_session.commit()
    await postgres_session.refresh(source)
    
    stats = {"item_count": 100}
    await repo.update_source_stats(source.id, stats)
    await postgres_session.refresh(source)
    
    assert source.last_synced_at is not None
    assert source.status == "waiting"
    assert source.config["last_stats"] == stats
    # Check if next_sync_at pushed forward (roughly)
    # On SQLite, datetimes might be returned as naive UTC.
    now = datetime.datetime.now(datetime.timezone.utc)
    next_sync = source.next_sync_at
    if next_sync.tzinfo is None:
        now = now.replace(tzinfo=None)
    assert next_sync > now

@pytest.mark.asyncio
async def test_category_mapping(postgres_session):
    repo = ParsingRepository(postgres_session)
    
    # Test get_or_create
    names = ["Cat A", "Cat B"]
    maps = await repo.get_or_create_category_maps(names)
    assert len(maps) == 2
    assert set(m.external_name for m in maps) == {"Cat A", "Cat B"}
    
    # Verify persistence
    unmapped = await repo.get_unmapped_categories()
    # Might be more if other tests run, but at least these 2
    external_names = [m.external_name for m in unmapped]
    assert "Cat A" in external_names
    
    # Test update mapping
    updates = [{"external_name": "Cat A", "internal_category_id": 99}]
    count = await repo.update_category_mappings(updates)
    assert count == 1
    
    # Verify update
    updated_maps = await repo.get_or_create_category_maps(["Cat A"])
    assert updated_maps[0].internal_category_id == 99

@pytest.mark.asyncio
async def test_upsert_source(postgres_session):
    repo = ParsingRepository(postgres_session)
    
    data = {
        "url": "http://upsert.com",
        "site_key": "upsert_key",
        "type": "hub",
        "strategy": "discovery"
    }
    
    # Create
    source = await repo.upsert_source(data)
    assert source.id is not None
    assert source.site_key == "upsert_key"
    
    # Update
    data["strategy"] = "deep"
    source_updated = await repo.upsert_source(data)
    assert source_updated.id == source.id
    assert source_updated.strategy == "deep"

@pytest.mark.asyncio
async def test_report_source_error(postgres_session):
    repo = ParsingRepository(postgres_session)
    
    source = ParsingSource(
        site_key="error_test",
        url="http://error.com",
        type="rss",
        strategy="simple"
    )
    postgres_session.add(source)
    await postgres_session.commit()
    
    # Report error (not broken yet)
    await repo.report_source_error(source.id, "Connection failed", is_broken=False)
    await postgres_session.refresh(source)
    
    assert source.status == "error"
    assert source.config["last_error"] == "Connection failed"
    assert source.config["retry_count"] == 1
    
    # Report broken
    await repo.report_source_error(source.id, "Fatal error", is_broken=True)
    await postgres_session.refresh(source)
    
    assert source.status == "broken"
    assert source.is_active is False
    assert source.config["fix_required"] is True

