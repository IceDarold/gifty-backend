from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from routes import internal as internal_routes


class _AllResult:
    def __init__(self, rows):
        self._rows = list(rows)

    def all(self):
        return list(self._rows)

    def scalars(self):
        return SimpleNamespace(all=lambda: list(self._rows))


@pytest.mark.asyncio
async def test_ops_sites_pipeline_active_and_queued(monkeypatch):
    now = datetime.now(timezone.utc)
    db = AsyncMock()

    monkeypatch.setattr(internal_routes, "_maybe_reconcile_queued_runs_with_rabbit", AsyncMock(return_value={"status": "ok"}), raising=True)
    monkeypatch.setattr(
        internal_routes,
        "_fetch_rabbit_queued_tasks",
        AsyncMock(
            return_value=[
                {"site_key": "site", "source_id": 1, "run_id": 2, "type": "list", "url": "u", "config": {"discovery_name": "Q"}},
                {"site_key": "other", "source_id": 9, "run_id": 9, "type": "hub", "url": "u"},
            ]
        ),
        raising=True,
    )
    monkeypatch.setattr(internal_routes, "_fetch_rabbit_queue_stats", AsyncMock(return_value={"status": "ok", "messages_total": 1}), raising=True)

    # get_ops_sites uses 5 db.execute calls.
    hub = SimpleNamespace(site_key="site", name="Site", url="u", status="waiting", is_active=True, last_synced_at=now)
    db.execute = AsyncMock(
        side_effect=[
            _AllResult([hub]),  # hubs
            _AllResult([("site", "running", 1)]),  # src_rows
            _AllResult([("site", "new", 2)]),  # disc_rows
            _AllResult([("site", 10)]),  # product_rows
            _AllResult([("site", 999, "waiting", True, "u", {"discovery_name": "Runtime"})]),  # hub_rows
        ]
    )
    sites = await internal_routes.get_ops_sites(db=db)
    assert sites["status"] == "ok"
    assert sites["items"][0]["counters"]["queued"] == 1
    assert sites["items"][0]["counters"]["products_total"] == 10

    # Pipeline endpoint: categories, list sources, runs.
    cat_new = SimpleNamespace(id=1, site_key="site", name="C1", url="c1", state="new", promoted_source_id=None, created_at=now)
    cat_prom = SimpleNamespace(id=2, site_key="site", name="C2", url="c2", state="promoted", promoted_source_id=10, created_at=now)
    src_running = SimpleNamespace(id=10, site_key="site", url="l1", type="list", status="running", is_active=True, priority=1, refresh_interval_hours=1, category_id=2, config={"discovery_name": "C2"}, updated_at=now)
    src_error = SimpleNamespace(id=11, site_key="site", url="l2", type="list", status="error", is_active=True, priority=1, refresh_interval_hours=1, category_id=1, config={"discovery_name": "C1"}, updated_at=now)
    run_completed = SimpleNamespace(id=100, source_id=10, status="completed", items_scraped=1, items_new=1, error_message=None, created_at=now, updated_at=now)
    run_src = SimpleNamespace(site_key="site", config={"discovery_name": "C2"})

    db.execute = AsyncMock(
        side_effect=[
            _AllResult([cat_new, cat_prom]),  # categories
            _AllResult([src_running, src_error]),  # list_sources
            _AllResult([(run_completed, run_src)]),  # runs
            _AllResult([src_running]),  # active runs: running_rows query
        ]
    )

    pipeline = await internal_routes.get_ops_site_pipeline(site_key="site", lane_limit=10, lane_offset=0, db=db)
    assert pipeline["status"] == "ok"
    assert pipeline["lane_totals"]["discovered:new"] == 1
    assert pipeline["lane_totals"]["queued"] == 1

    active = await internal_routes.get_ops_active_runs(limit=10, db=db)
    assert active["status"] == "ok"
    assert any(i["status"] == "queued" for i in active["items"])
    assert any(i["status"] == "running" for i in active["items"])

    queued = await internal_routes.get_ops_queued_runs(limit=10, offset=0, db=db)
    assert queued["status"] == "ok"
    assert queued["total"] == 1
