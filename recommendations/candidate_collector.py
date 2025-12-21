from __future__ import annotations

from typing import Any, Optional

from integrations.takprodam.models import GiftCandidate
from integrations.takprodam.search import search_gift_candidates

from .cache import default_cache
from .query_rules_loader import load_ruleset


_CACHE = default_cache()
_RULESET_PATH = "config/gift_query_rules.v1.yaml"


def _normalize_query(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized or None


def _load_negative_keywords() -> list[str]:
    try:
        ruleset = load_ruleset(_RULESET_PATH)
    except ValueError:
        return []

    banned = ruleset.get("banned", {})
    if not isinstance(banned, dict):
        return []

    keywords = []
    for item in banned.get("negative_keywords", []) or []:
        normalized = _normalize_query(item)
        if normalized:
            keywords.append(normalized)
    return keywords


def filter_candidates(candidates: list[GiftCandidate], negative_keywords: list[str]) -> list[GiftCandidate]:
    if not candidates:
        return []

    normalized_keywords = [kw.lower() for kw in negative_keywords if isinstance(kw, str) and kw.strip()]
    if not normalized_keywords:
        return [candidate for candidate in candidates if candidate.title and candidate.product_url]

    filtered: list[GiftCandidate] = []
    for candidate in candidates:
        if not candidate.title or not candidate.product_url:
            continue
        haystack = " ".join(
            part
            for part in [candidate.title, candidate.description or ""]
            if isinstance(part, str)
        ).lower()
        if any(keyword in haystack for keyword in normalized_keywords):
            continue
        filtered.append(candidate)
    return filtered


def collect_candidates(
    queries: list[dict],
    *,
    per_query_limit: int = 50,
    max_queries: int = 10,
    source_id: int | None = None,
    use_cache: bool = True,
    disable_cache: bool = False,
) -> tuple[list[GiftCandidate], dict]:
    if disable_cache:
        use_cache = False

    selected = queries[:max_queries]

    per_query_stats: list[dict[str, Any]] = []
    empty_queries: list[str] = []
    cache_hits = 0
    cache_misses = 0
    raw_candidates: list[GiftCandidate] = []

    for payload in selected:
        query_value = payload.get("query") if isinstance(payload, dict) else None
        normalized_query = _normalize_query(query_value)
        if not normalized_query:
            continue

        key = f"takprodam:{source_id}:{normalized_query}:{per_query_limit}"
        candidates: list[GiftCandidate] = []
        cache_hit = False

        if use_cache:
            cached = _CACHE.get(key)
            if cached is not None:
                candidates = cached
                cache_hit = True
                cache_hits += 1
            else:
                cache_misses += 1
        else:
            cache_misses += 1

        if not cache_hit:
            candidates = search_gift_candidates(
                query=normalized_query,
                limit=per_query_limit,
                source_id=source_id,
            )
            if use_cache:
                _CACHE.set(key, candidates)

        raw_candidates.extend(candidates)
        count = len(candidates)
        if count == 0:
            empty_queries.append(normalized_query)

        per_query_stats.append(
            {
                "query": normalized_query,
                "bucket": payload.get("bucket") if isinstance(payload, dict) else None,
                "reason": payload.get("reason") if isinstance(payload, dict) else None,
                "count": count,
                "cache": cache_hit,
            }
        )

    unique: dict[str, GiftCandidate] = {}
    for candidate in raw_candidates:
        if candidate.gift_id not in unique:
            unique[candidate.gift_id] = candidate

    negative_keywords = _load_negative_keywords()
    filtered_candidates = filter_candidates(list(unique.values()), negative_keywords)

    debug = {
        "max_queries": max_queries,
        "per_query_limit": per_query_limit,
        "cache": {"enabled": use_cache, "hits": cache_hits, "misses": cache_misses},
        "per_query": per_query_stats,
        "empty_queries": empty_queries,
        "total_raw": len(raw_candidates),
        "total_unique": len(unique),
        "filtered_out": len(unique) - len(filtered_candidates),
    }

    return filtered_candidates, debug
