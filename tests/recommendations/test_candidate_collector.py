import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from integrations.takprodam.models import GiftCandidate
from recommendations import candidate_collector
from recommendations.cache import TTLCache


def _make_candidate(gift_id: str, title: str = "Item") -> GiftCandidate:
    return GiftCandidate(
        gift_id=gift_id,
        title=title,
        description=None,
        price=None,
        currency=None,
        image_url=None,
        product_url="https://example.com/item",
        merchant=None,
        category=None,
        raw={},
    )


def test_cache_hits_and_debug(monkeypatch):
    calls = {"count": 0}

    def _search(query, limit=50, source_id=None):
        calls["count"] += 1
        return [_make_candidate(f"takprodam:{query}")]

    monkeypatch.setattr(candidate_collector, "search_gift_candidates", _search)
    candidate_collector._CACHE = TTLCache(ttl_seconds=3600, max_items=10)

    queries = [{"query": "Плед", "bucket": "vibe", "reason": "adult.cozy"}]

    result1, debug1 = candidate_collector.collect_candidates(queries)
    result2, debug2 = candidate_collector.collect_candidates(queries)

    assert calls["count"] == 1
    assert len(result1) == 1
    assert len(result2) == 1
    assert debug1["cache"]["hits"] == 0
    assert debug2["cache"]["hits"] == 1


def test_dedup_by_gift_id():
    def _search(query, limit=50, source_id=None):
        return [_make_candidate("takprodam:1"), _make_candidate("takprodam:1")]

    candidate_collector.search_gift_candidates = _search
    candidate_collector._CACHE = TTLCache(ttl_seconds=3600, max_items=10)

    queries = [
        {"query": "A", "bucket": "age_base", "reason": "adult"},
        {"query": "B", "bucket": "vibe", "reason": "adult.cozy"},
    ]

    result, debug = candidate_collector.collect_candidates(queries, use_cache=False)

    assert len(result) == 1
    assert debug["total_unique"] == 1


def test_negative_keywords_filter(monkeypatch):
    def _search(query, limit=50, source_id=None):
        return [
            _make_candidate("takprodam:1", title="Эротика"),
            _make_candidate("takprodam:2", title="Плед"),
        ]

    monkeypatch.setattr(candidate_collector, "search_gift_candidates", _search)
    monkeypatch.setattr(candidate_collector, "_load_negative_keywords", lambda: ["эрот"])
    candidate_collector._CACHE = TTLCache(ttl_seconds=3600, max_items=10)

    queries = [{"query": "Плед", "bucket": "vibe", "reason": "adult.cozy"}]

    result, debug = candidate_collector.collect_candidates(queries, use_cache=False)

    assert len(result) == 1
    assert result[0].gift_id == "takprodam:2"
    assert debug["filtered_out"] == 1


def test_empty_query_is_tracked(monkeypatch):
    def _search(query, limit=50, source_id=None):
        return []

    monkeypatch.setattr(candidate_collector, "search_gift_candidates", _search)
    candidate_collector._CACHE = TTLCache(ttl_seconds=3600, max_items=10)

    queries = [{"query": "Плед", "bucket": "vibe", "reason": "adult.cozy"}]

    result, debug = candidate_collector.collect_candidates(queries, use_cache=False)

    assert result == []
    assert debug["empty_queries"] == ["плед"]
