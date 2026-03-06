from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models import CategoryMap, ParsingHub, ParsingSource
from app.repositories.parsing import ParsingRepository


@pytest.mark.asyncio
async def test_upsert_source_create_and_update(postgres_session):
    repo = ParsingRepository(postgres_session)

    created = await repo.upsert_source(
        {
            "site_key": "mrgeek",
            "url": "https://mrgeek.ru/hub",
            "type": "hub",
            "strategy": "discovery",
            "is_active": True,
            "status": "waiting",
        }
    )
    assert created.id
    assert created.is_active is True

    updated = await repo.upsert_source(
        {
            "site_key": "mrgeek",
            "url": "https://mrgeek.ru/hub",
            "is_active": False,
            "status": "disabled",
        }
    )
    assert updated.id == created.id
    assert updated.is_active is False
    assert updated.status == "disabled"


@pytest.mark.asyncio
async def test_get_due_sources_orders_by_priority_and_next_sync(postgres_session):
    repo = ParsingRepository(postgres_session)
    now = datetime.now(timezone.utc)

    s1 = ParsingSource(site_key="a", url="https://a/1", type="hub", is_active=True, priority=10, next_sync_at=now - timedelta(minutes=10))
    s2 = ParsingSource(site_key="a", url="https://a/2", type="hub", is_active=True, priority=50, next_sync_at=now - timedelta(minutes=5))
    s3 = ParsingSource(site_key="a", url="https://a/3", type="hub", is_active=True, priority=50, next_sync_at=now + timedelta(hours=1))
    postgres_session.add_all([s1, s2, s3])
    await postgres_session.commit()

    due = await repo.get_due_sources(limit=10)
    assert [s.url for s in due][:2] == ["https://a/2", "https://a/1"]
    assert all(s.url != "https://a/3" for s in due)


@pytest.mark.asyncio
async def test_report_source_error_retry_and_broken(postgres_session):
    repo = ParsingRepository(postgres_session)
    src = ParsingSource(site_key="t", url="https://t/1", type="hub", is_active=True, status="waiting", config={})
    postgres_session.add(src)
    await postgres_session.commit()
    await postgres_session.refresh(src)

    out = await repo.report_source_error(src.id, "oops", is_broken=False)
    assert out is not None
    assert out.status == "error"
    assert (out.config or {}).get("retry_count") == 1
    assert out.is_active is True

    out2 = await repo.report_source_error(src.id, "bad", is_broken=True)
    assert out2 is not None
    assert out2.status == "broken"
    assert out2.is_active is False
    assert (out2.config or {}).get("fix_required") is True


@pytest.mark.asyncio
async def test_get_or_create_category_maps_and_update_mappings(postgres_session):
    repo = ParsingRepository(postgres_session)

    maps = await repo.get_or_create_category_maps(["A", "B", "A"])
    assert {m.external_name for m in maps} == {"A", "B"}

    updated = await repo.update_category_mappings(
        [
            {"external_name": "A", "internal_category_id": 10},
            {"external_name": "B", "internal_category_id": 20},
        ]
    )
    assert updated == 2

    rows = (await postgres_session.execute(select(CategoryMap))).scalars().all()
    by_name = {r.external_name: r.internal_category_id for r in rows}
    assert by_name["A"] == 10
    assert by_name["B"] == 20


@pytest.mark.asyncio
async def test_sync_spiders_creates_hub_and_runtime_source(postgres_session):
    repo = ParsingRepository(postgres_session)

    new = await repo.sync_spiders(["sp1"], default_urls={"sp1": "https://sp1.example"})
    assert new == ["sp1"]

    hub = (await postgres_session.execute(select(ParsingHub).where(ParsingHub.site_key == "sp1"))).scalar_one()
    assert hub.url == "https://sp1.example"

    runtime = (
        await postgres_session.execute(
            select(ParsingSource).where(ParsingSource.site_key == "sp1", ParsingSource.type == "hub")
        )
    ).scalar_one()
    assert runtime.url == "https://sp1.example"

    new2 = await repo.sync_spiders(["sp1"], default_urls={"sp1": "https://sp1.example"})
    assert new2 == []


@pytest.mark.asyncio
async def test_get_or_create_merchant(postgres_session):
    repo = ParsingRepository(postgres_session)
    m1 = await repo.get_or_create_merchant("mrgeek")
    assert m1 is not None
    assert m1.site_key == "mrgeek"
    assert m1.name == "mrgeek"

    await postgres_session.flush()
    m2 = await repo.get_or_create_merchant("mrgeek")
    assert m2 is not None
    assert m2.id == m1.id


@pytest.mark.asyncio
async def test_parsing_runs_create_update_and_history(postgres_session):
    repo = ParsingRepository(postgres_session)
    src = ParsingSource(site_key="t", url="https://t/hub", type="hub", is_active=True, status="waiting", priority=10)
    postgres_session.add(src)
    await postgres_session.commit()
    await postgres_session.refresh(src)

    run = await repo.create_parsing_run(
        source_id=src.id,
        status="completed",
        items_scraped=10,
        items_new=2,
        error_message=None,
        duration_seconds=1.5,
        logs="ok",
    )
    assert run.id

    updated = await repo.update_parsing_run(run.id, status="error", error_message="boom", logs="ERR")
    assert updated is not None
    assert updated.status == "error"

    missing = await repo.update_parsing_run(999999, status="completed")
    assert missing is None

    history = await repo.get_source_history(src.id, limit=10)
    assert history
    assert history[0].id == run.id


@pytest.mark.asyncio
async def test_discovered_category_flow_and_activate_sources(postgres_session):
    repo = ParsingRepository(postgres_session)

    created = await repo.upsert_discovered_category(
        {"site_key": "s", "url": "https://s/cat", "name": "Cats", "parent_url": "https://s", "state": "new"}
    )
    assert created.id

    updated = await repo.upsert_discovered_category(
        {"site_key": "s", "url": "https://s/cat", "name": "Cats v2", "state": "new"}
    )
    assert updated.id == created.id
    assert updated.name == "Cats v2"

    source = await repo.promote_discovered_category(created.id)
    assert source is not None
    assert source.type == "list"
    assert source.category_id == created.id

    cats = await repo.get_discovered_categories(limit=10, states=["promoted"])
    assert any(c.id == created.id for c in cats)
    assert await repo.count_promoted_categories_today() >= 1
    assert await repo.count_discovered_today() >= 1

    # get_discovered_sources should return sources for "new" categories when promoted_source_id set.
    orphan_source = ParsingSource(site_key="s", url="https://s/other", type="hub", is_active=True, status="waiting", priority=10)
    postgres_session.add(orphan_source)
    await postgres_session.commit()
    await postgres_session.refresh(orphan_source)
    new_cat = await repo.upsert_discovered_category(
        {"site_key": "s", "url": "https://s/new", "name": "New", "parent_url": None, "state": "new", "promoted_source_id": orphan_source.id}
    )
    await postgres_session.commit()

    sources = await repo.get_discovered_sources(limit=10)
    assert any(s.id == orphan_source.id for s in sources)

    promoted = await repo.activate_sources([new_cat.id])
    assert promoted == 1

    missing = await repo.promote_discovered_category(999999)
    assert missing is None
