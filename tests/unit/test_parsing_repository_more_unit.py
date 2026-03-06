from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.repositories.parsing import ParsingRepository


class _Res:
    def __init__(self, *, all_rows=None, scalar_value=None, one=None, scalars_items=None, rowcount=0):
        self._all_rows = all_rows
        self._scalar_value = scalar_value
        self._one = one
        self._scalars_items = scalars_items
        self.rowcount = rowcount

    def all(self):
        return list(self._all_rows or [])

    def scalar(self):
        return self._scalar_value

    def one_or_none(self):
        return self._one

    def scalars(self):
        return SimpleNamespace(all=lambda: list(self._scalars_items or []))

    def scalar_one_or_none(self):
        return (self._scalars_items or [None])[0]


@pytest.mark.anyio
async def test_get_sites_monitoring_maps_statuses():
    session = AsyncMock()
    now = datetime.now(timezone.utc)
    rows = [
        SimpleNamespace(
            site_key="s",
            first_id=1,
            first_url="u",
            total_sources=2,
            running_count=1,
            queued_count=0,
            error_count=0,
            broken_count=0,
            last_synced_at=now,
        ),
    ]
    session.execute = AsyncMock(return_value=_Res(all_rows=rows))
    repo = ParsingRepository(session)
    out = await repo.get_sites_monitoring()
    assert out[0]["status"] == "running"
    assert out[0]["last_synced_at"]


@pytest.mark.anyio
async def test_get_24h_stats_handles_none_row():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_Res(one=None))
    repo = ParsingRepository(session)
    out = await repo.get_24h_stats()
    assert out == {"scraped_24h": 0, "new_24h": 0}

    session.execute = AsyncMock(return_value=_Res(one=SimpleNamespace(scraped=5, new=2)))
    out2 = await repo.get_24h_stats()
    assert out2["scraped_24h"] == 5


@pytest.mark.anyio
async def test_get_aggregate_history_returns_rows():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_Res(all_rows=[("d", 1, 2)]))
    repo = ParsingRepository(session)
    out = await repo.get_aggregate_history("s", limit_days=2)
    assert out == [("d", 1, 2)]


@pytest.mark.anyio
async def test_mark_missing_spiders_marks_hubs_and_hub_sources_and_returns_report():
    session = AsyncMock()
    session.commit = AsyncMock()

    hub = SimpleNamespace(site_key="miss", url="u", config={}, is_active=True, status="waiting")
    hub_source = SimpleNamespace(site_key="miss", type="hub", url="u", config={}, is_active=True, status="waiting")

    session.execute = AsyncMock(
        side_effect=[
            _Res(scalars_items=[hub]),  # hubs not in available
            _Res(scalars_items=[hub_source]),  # hub mirror sources
        ]
    )

    repo = ParsingRepository(session)
    now = datetime(2026, 3, 6, 12, 0, 0, tzinfo=timezone.utc)
    out = await repo.mark_missing_spiders(["present"], grace_minutes=60, now=now)

    assert out["missing_spiders"] == ["miss"]
    assert out["newly_missing_spiders"] == ["miss"]
    assert out["disabled_spiders"] == []
    assert out["grace_minutes"] == 60
    assert out["ts"] == now.isoformat()

    assert hub.is_active is False
    assert hub.status == "missing"
    assert hub.config["missing_in_code"] is True
    assert hub.config["missing_in_code_since"] == now.isoformat()
    assert hub.config["missing_in_code_last_seen_at"] == now.isoformat()

    assert hub_source.is_active is False
    assert hub_source.status == "missing"
    assert hub_source.config["missing_in_code"] is True
    assert hub_source.config["disabled_due_to_missing_in_code"] is True

    session.commit.assert_awaited()


@pytest.mark.anyio
async def test_get_missing_spiders_report_empty_when_no_missing_flags():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_Res(scalars_items=[SimpleNamespace(site_key="ok", config={})]))
    repo = ParsingRepository(session)
    out = await repo.get_missing_spiders_report(limit=10)
    assert out == []
    assert session.execute.await_count == 1


@pytest.mark.anyio
async def test_get_missing_spiders_report_includes_stats():
    session = AsyncMock()
    hub = SimpleNamespace(
        site_key="miss",
        url="u",
        config={"missing_in_code": True, "missing_in_code_since": "t0", "missing_in_code_last_seen_at": "t1"},
    )
    rows = [
        SimpleNamespace(
            site_key="miss",
            sources_total=3,
            sources_active=1,
            sources_missing=1,
            sources_disabled=1,
        )
    ]
    session.execute = AsyncMock(
        side_effect=[
            _Res(scalars_items=[hub]),
            _Res(all_rows=rows),
        ]
    )
    repo = ParsingRepository(session)
    out = await repo.get_missing_spiders_report(limit=10)
    assert out and out[0]["site_key"] == "miss"
    assert out[0]["hub_url"] == "u"
    assert out[0]["stats"]["sources_total"] == 3
    assert out[0]["hub_config"]["missing_in_code"] is True


@pytest.mark.anyio
async def test_get_last_full_cycle_stats_no_hub_time_and_with_time():
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[_Res(scalar_value=None)])
    repo = ParsingRepository(session)
    assert await repo.get_last_full_cycle_stats("s") == 0

    hub_time = datetime.now(timezone.utc) - timedelta(days=1)
    session.execute = AsyncMock(side_effect=[_Res(scalar_value=hub_time), _Res(scalar_value=7)])
    assert await repo.get_last_full_cycle_stats("s") == 7


@pytest.mark.anyio
async def test_get_total_category_products_count_missing_and_present():
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[_Res(scalars_items=[None])])
    repo = ParsingRepository(session)
    assert await repo.get_total_category_products_count("s", "c") == 0

    cat = SimpleNamespace(id=10)
    session.execute = AsyncMock(side_effect=[_Res(scalars_items=[cat]), _Res(scalar_value=3)])
    assert await repo.get_total_category_products_count("s", "c") == 3


@pytest.mark.anyio
async def test_upsert_product_category_links_empty_and_rowcount():
    session = AsyncMock()
    repo = ParsingRepository(session)
    assert await repo.upsert_product_category_links(product_ids=set(), discovered_category_id=1, source_id=1) == 0

    session.execute = AsyncMock(return_value=_Res(rowcount=2))
    out = await repo.upsert_product_category_links(product_ids={"p1", "p2"}, discovered_category_id=1, source_id=1, run_id=5)
    assert out == 2


@pytest.mark.anyio
async def test_get_source_daily_history_returns_all():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_Res(all_rows=[("d", 1, 2)]))
    repo = ParsingRepository(session)
    out = await repo.get_source_daily_history(1, limit_days=2)
    assert out == [("d", 1, 2)]


@pytest.mark.anyio
async def test_get_active_workers_reads_redis():
    # use FakeRedis from internal conftest? It doesn't implement keys(); use custom redis stub here.
    redis = SimpleNamespace(
        keys=AsyncMock(return_value=["worker_heartbeat:1", "worker_heartbeat:2"]),
        get=AsyncMock(side_effect=[json.dumps({"id": "w1"}), "{bad-json"]),
    )
    session = AsyncMock()
    repo = ParsingRepository(session, redis=redis)
    out = await repo.get_active_workers()
    assert out == [{"id": "w1"}]


@pytest.mark.anyio
async def test_get_active_workers_no_redis_returns_empty():
    repo = ParsingRepository(AsyncMock(), redis=None)
    assert await repo.get_active_workers() == []


@pytest.mark.anyio
async def test_get_all_active_sources_and_all_sources():
    session = AsyncMock()
    a = SimpleNamespace(id=1)
    b = SimpleNamespace(id=2)
    session.execute = AsyncMock(side_effect=[_Res(scalars_items=[a]), _Res(scalars_items=[b])])
    repo = ParsingRepository(session)

    out1 = await repo.get_all_active_sources()
    out2 = await repo.get_all_sources()
    assert out1 == [a]
    assert out2 == [b]


@pytest.mark.anyio
async def test_get_due_sources_returns_scalars():
    session = AsyncMock()
    src = SimpleNamespace(id=1)
    session.execute = AsyncMock(return_value=_Res(scalars_items=[src]))
    repo = ParsingRepository(session)
    out = await repo.get_due_sources(limit=1)
    assert out == [src]


@pytest.mark.anyio
async def test_get_or_create_category_maps_empty_names_short_circuit():
    repo = ParsingRepository(AsyncMock())
    assert await repo.get_or_create_category_maps([]) == []


@pytest.mark.anyio
async def test_get_or_create_category_maps_returns_existing_without_inserts():
    session = AsyncMock()
    session.bind = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))
    m = SimpleNamespace(external_name="a")
    session.execute = AsyncMock(return_value=_Res(scalars_items=[m]))
    repo = ParsingRepository(session)
    out = await repo.get_or_create_category_maps(["a"])
    assert out == [m]


@pytest.mark.anyio
async def test_update_category_mappings_empty_returns_zero():
    repo = ParsingRepository(AsyncMock())
    assert await repo.update_category_mappings([]) == 0


@pytest.mark.anyio
async def test_update_category_mappings_updates_rows_and_commits():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_Res(rowcount=1))
    session.commit = AsyncMock()
    repo = ParsingRepository(session)
    out = await repo.update_category_mappings([{"external_name": "a", "internal_category_id": 1}])
    assert out == 1
    session.commit.assert_awaited()


@pytest.mark.anyio
async def test_report_source_error_returns_none_when_source_missing():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_Res(scalars_items=[None]))
    repo = ParsingRepository(session)
    assert await repo.report_source_error(1, "oops", is_broken=True) is None


@pytest.mark.anyio
async def test_sync_spiders_updates_placeholder_urls_when_default_url_provided():
    session = AsyncMock()
    session.commit = AsyncMock()
    hub = SimpleNamespace(site_key="s1", url="https://s1.placeholder", config={}, status="waiting")
    src = SimpleNamespace(site_key="s1", type="hub", url="https://s1.placeholder", config={}, status="waiting")

    session.execute = AsyncMock(
        side_effect=[
            _Res(scalars_items=[hub]),  # existing hubs
            _Res(scalars_items=[src]),  # existing runtime hub source
        ]
    )
    repo = ParsingRepository(session)
    out = await repo.sync_spiders(["s1"], default_urls={"s1": "https://real.example/s1"})
    assert out == []
    assert hub.url == "https://real.example/s1"
    assert src.url == "https://real.example/s1"
    session.commit.assert_awaited()


@pytest.mark.anyio
async def test_set_source_status_executes_update_and_commits():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_Res(rowcount=1))
    session.commit = AsyncMock()
    repo = ParsingRepository(session)
    await repo.set_source_status(1, "waiting")
    session.commit.assert_awaited()


@pytest.mark.anyio
async def test_reset_source_error_handles_none_config_and_removes_fields():
    session = AsyncMock()
    session.commit = AsyncMock()
    source = SimpleNamespace(config=None)
    session.execute = AsyncMock(return_value=_Res(scalars_items=[source]))
    repo = ParsingRepository(session)
    await repo.reset_source_error(1)
    assert isinstance(source.config, dict)
    session.commit.assert_awaited()


@pytest.mark.anyio
async def test_update_source_updates_fields_and_refreshes():
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    src = SimpleNamespace(url="u", status="waiting")
    session.execute = AsyncMock(return_value=_Res(scalars_items=[src]))
    repo = ParsingRepository(session)

    out = await repo.update_source(1, {"status": "running", "unknown": 1})
    assert out is src
    assert src.status == "running"
    session.refresh.assert_awaited()

    session.execute = AsyncMock(return_value=_Res(scalars_items=[None]))
    assert await repo.update_source(1, {"status": "x"}) is None


@pytest.mark.anyio
async def test_log_parsing_run_and_update_parsing_run_cover_updates():
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = lambda _obj: None
    repo = ParsingRepository(session)

    run = await repo.log_parsing_run(1, status="completed", items_scraped=2, items_new=1, error_message=None)
    assert run.source_id == 1

    existing = SimpleNamespace(id=1, status="queued", items_scraped=0, items_new=0, error_message=None, duration_seconds=None, logs=None)
    session.execute = AsyncMock(return_value=_Res(scalars_items=[existing]))
    out = await repo.update_parsing_run(
        1,
        status="completed",
        items_scraped=2,
        items_new=1,
        error_message="x",
        duration_seconds=1.5,
        logs="l",
    )
    assert out is existing
    assert existing.items_scraped == 2
    assert existing.items_new == 1
    assert existing.duration_seconds == 1.5

    session.execute = AsyncMock(return_value=_Res(scalars_items=[None]))
    assert await repo.update_parsing_run(999, status="x") is None


@pytest.mark.anyio
async def test_get_total_products_count_reads_scalar():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_Res(scalar_value=9))
    repo = ParsingRepository(session)
    assert await repo.get_total_products_count("s") == 9


@pytest.mark.anyio
async def test_get_aggregate_status_branches():
    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[
            _Res(scalars_items=["running"]),
            _Res(scalars_items=["queued"]),
            _Res(scalars_items=["error"]),
            _Res(scalars_items=["broken"]),
            _Res(scalars_items=["waiting"]),
        ]
    )
    repo = ParsingRepository(session)
    assert await repo.get_aggregate_status("s") == "running"
    assert await repo.get_aggregate_status("s") == "queued"
    assert await repo.get_aggregate_status("s") == "error"
    assert await repo.get_aggregate_status("s") == "broken"
    assert await repo.get_aggregate_status("s") == "waiting"


@pytest.mark.anyio
async def test_get_sites_monitoring_broken_branch():
    session = AsyncMock()
    now = datetime.now(timezone.utc)
    rows = [
        SimpleNamespace(
            site_key="s",
            first_id=1,
            first_url="u",
            total_sources=2,
            running_count=0,
            queued_count=0,
            error_count=0,
            broken_count=1,
            last_synced_at=now,
        ),
    ]
    session.execute = AsyncMock(return_value=_Res(all_rows=rows))
    repo = ParsingRepository(session)
    out = await repo.get_sites_monitoring()
    assert out[0]["status"] == "broken"


@pytest.mark.anyio
async def test_get_or_create_merchant_empty_key_returns_none():
    repo = ParsingRepository(AsyncMock())
    assert await repo.get_or_create_merchant("") is None


@pytest.mark.anyio
async def test_get_source_by_url_and_hub_by_site_key():
    session = AsyncMock()
    src = SimpleNamespace(id=1)
    hub = SimpleNamespace(site_key="s")
    session.execute = AsyncMock(side_effect=[_Res(scalars_items=[src]), _Res(scalars_items=[hub])])
    repo = ParsingRepository(session)
    assert await repo.get_source_by_url("u") is src
    assert await repo.get_hub_by_site_key("s") is hub


@pytest.mark.anyio
async def test_promote_discovered_category_updates_existing_source_config(monkeypatch):
    session = AsyncMock()
    session.flush = AsyncMock()
    category = SimpleNamespace(id=7, site_key="s", url="u", name="Cat", parent_url="p", state="new", promoted_source_id=None)
    source = SimpleNamespace(
        id=10,
        is_active=False,
        status="disabled",
        category_id=None,
        config={},
        next_sync_at=None,
    )
    session.execute = AsyncMock(side_effect=[_Res(scalars_items=[category]), _Res(scalars_items=[source])])

    repo = ParsingRepository(session)
    out = await repo.promote_discovered_category(7)
    assert out is source
    assert source.is_active is True
    assert source.category_id == 7
    assert source.config["discovery_name"] == "Cat"
    assert category.promoted_source_id == 10


@pytest.mark.anyio
async def test_upsert_discovered_category_updates_existing():
    session = AsyncMock()
    session.flush = AsyncMock()
    existing = SimpleNamespace(site_key="s", url="u", name="Old", parent_url=None)
    session.execute = AsyncMock(return_value=_Res(scalars_items=[existing]))
    repo = ParsingRepository(session)
    out = await repo.upsert_discovered_category({"site_key": "s", "url": "u", "name": "New", "parent_url": None})
    assert out is existing
    assert existing.name == "New"


@pytest.mark.anyio
async def test_promote_discovered_category_creates_new_source_when_missing():
    session = AsyncMock()
    session.flush = AsyncMock()
    category = SimpleNamespace(id=7, site_key="s", url="u", name="Cat", parent_url="p", state="new", promoted_source_id=None)
    session.execute = AsyncMock(side_effect=[_Res(scalars_items=[category]), _Res(scalars_items=[None])])
    session.add = lambda _obj: None
    repo = ParsingRepository(session)
    out = await repo.promote_discovered_category(7)
    assert out is not None
    assert category.state == "promoted"


@pytest.mark.anyio
async def test_activate_sources_promotes_and_sets_next_sync_at(monkeypatch):
    session = AsyncMock()
    session.commit = AsyncMock()
    repo = ParsingRepository(session)
    src = SimpleNamespace(next_sync_at=None)
    repo.promote_discovered_category = AsyncMock(return_value=src)
    out = await repo.activate_sources([1, 2])
    assert out == 2
    assert repo.promote_discovered_category.await_count == 2
    session.commit.assert_awaited()


@pytest.mark.anyio
async def test_get_discovered_sources_and_activate_sources_empty_short_circuits():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_Res(scalars_items=[]))
    repo = ParsingRepository(session)
    assert await repo.get_discovered_sources(limit=5) == []
    assert await repo.activate_sources([]) == 0
