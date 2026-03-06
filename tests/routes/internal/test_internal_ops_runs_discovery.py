from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from routes import internal as internal_routes


class _FirstResult:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class _AllResult:
    def __init__(self, rows):
        self._rows = list(rows)

    def all(self):
        return list(self._rows)

    def scalars(self):
        return SimpleNamespace(all=lambda: list(self._rows))

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None


@pytest.mark.asyncio
async def test_ops_run_details_synthetic_queued_and_running(monkeypatch):
    db = AsyncMock()

    # Not found in DB -> synthetic queued branch.
    db.execute = AsyncMock(return_value=_FirstResult(None))
    monkeypatch.setattr(
        internal_routes,
        "_fetch_rabbit_queued_tasks",
        AsyncMock(return_value=[{"site_key": "s", "source_id": 1, "run_id": 2, "type": "list", "url": "u", "config": {"discovery_name": "C"}}]),
        raising=True,
    )
    synthetic_queued_id = 2_000_000_000  # idx 0
    out = await internal_routes.get_ops_run_details(run_id=synthetic_queued_id, db=db)
    assert out["item"]["run_status"] == "queued"
    assert out["item"]["category_name"] == "C"

    # Synthetic running branch: source exists in DB.
    now = datetime.now(timezone.utc)
    src = SimpleNamespace(id=5, site_key="s", url="u", type="hub", config={"last_logs": "x"}, updated_at=now)
    db.execute = AsyncMock(side_effect=[_FirstResult(None), _AllResult([src])])
    synthetic_running_id = 1_000_000_000 + 5
    out2 = await internal_routes.get_ops_run_details(run_id=synthetic_running_id, db=db)
    assert out2["item"]["run_status"] == "running"
    assert out2["item"]["logs"] == "x"


@pytest.mark.asyncio
async def test_ops_run_details_persisted(monkeypatch):
    db = AsyncMock()
    now = datetime.now(timezone.utc)
    run = SimpleNamespace(
        id=1,
        source_id=10,
        status="completed",
        duration_seconds=None,
        created_at=now,
        updated_at=now,
        logs="Batch ingested: 1 products, 3 categories",
        items_scraped=1,
        items_new=1,
        error_message=None,
    )
    source = SimpleNamespace(site_key="s", url="u", type="list", config={"discovery_name": "D"})
    category = SimpleNamespace(name="Cat")
    db.execute = AsyncMock(return_value=_FirstResult((run, source, category)))
    out = await internal_routes.get_ops_run_details(run_id=1, db=db)
    assert out["item"]["categories_scraped"] == 3
    assert out["item"]["category_name"] == "Cat"


@pytest.mark.asyncio
async def test_retry_ops_run_publishes_and_sets_queued(monkeypatch, fake_redis):
    now = datetime.now(timezone.utc)
    run = SimpleNamespace(id=1, source_id=10)
    source = SimpleNamespace(id=10, url="u", site_key="s", type="hub", strategy="discovery", config={})
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_FirstResult((run, source)))

    publish = lambda task: True
    monkeypatch.setattr(internal_routes, "_fetch_rabbit_queue_stats", AsyncMock(return_value={"status": "ok", "messages_total": 1}), raising=True)
    monkeypatch.setattr("app.utils.rabbitmq.publish_parsing_task", publish, raising=False)

    class _Repo:
        def __init__(self, db):
            pass

        async def set_queued(self, source_id: int):
            return None

    monkeypatch.setattr(internal_routes, "ParsingRepository", _Repo, raising=True)

    out = await internal_routes.retry_ops_run(run_id=1, db=db, redis=fake_redis)
    assert out["status"] == "ok"


@pytest.mark.asyncio
async def test_ops_discovery_categories_list_and_actions(monkeypatch, fake_redis):
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    now = datetime.now(timezone.utc)
    category = SimpleNamespace(
        id=1,
        hub_id=None,
        site_key="s",
        url="u",
        name="Cat",
        parent_url=None,
        state="new",
        promoted_source_id=None,
        created_at=now,
        updated_at=now,
    )

    class _Scalar:
        def __init__(self, value):
            self._value = value

        def scalar(self):
            return self._value

    class _Rowcount:
        def __init__(self, rowcount: int):
            self.rowcount = rowcount

    # list: count + rows (tuple of (DiscoveredCategory, products_total, last_run_at))
    db.execute = AsyncMock(
        side_effect=[
            _Scalar(1),
            _AllResult([(category, 3, now)]),
            # details: category + products_total
            _AllResult([category]),
            _Scalar(5),
            # promote: ParsingRepository.activate_sources
            # reject/reactivate: update rowcount results
            _Rowcount(2),
            _Rowcount(3),
        ]
    )

    listed = await internal_routes.get_ops_discovery_categories(db=db, state="new", site_key=None, q=None, limit=10, offset=0)
    assert listed["total"] == 1
    assert listed["items"][0]["products_total"] == 3

    details = await internal_routes.get_ops_discovery_category_details(category_id=1, db=db)
    assert details["item"]["products_total"] == 5
    assert details["item"]["runtime_source"] is None

    repo = SimpleNamespace(activate_sources=AsyncMock(return_value=7))
    monkeypatch.setattr(internal_routes, "ParsingRepository", lambda db: repo, raising=True)
    prom = await internal_routes.promote_ops_discovery_categories(category_ids=[1, 2], db=db)
    assert prom["activated_count"] == 7

    rej = await internal_routes.reject_ops_discovery_categories(category_ids=[1], db=db)
    assert rej["updated"] == 2
    rea = await internal_routes.reactivate_ops_discovery_categories(category_ids=[1], db=db)
    assert rea["updated"] == 3
