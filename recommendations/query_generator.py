from __future__ import annotations

from typing import Any

from .age_segment import get_age_segment
from .models import QuizAnswers


BucketItem = dict[str, str]


def _normalize_query(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized or None


def _collect_bucket(queries: list[Any], bucket: str, reason: str) -> list[BucketItem]:
    items: list[BucketItem] = []
    for query in queries:
        normalized = _normalize_query(query)
        if normalized:
            items.append({"query": normalized, "bucket": bucket, "reason": reason})
    return items


def generate_queries(quiz: QuizAnswers, ruleset: dict[str, Any]) -> list[dict[str, str]]:
    limits = ruleset.get("limits", {})
    max_per_bucket = int(limits.get("max_queries_per_bucket", 0))
    max_total = int(limits.get("max_queries_total", 0))
    min_total = int(limits.get("min_queries_total", 0))
    max_kw_from_desc = int(limits.get("max_keywords_from_description", 0))

    banned = ruleset.get("banned", {})
    banned_queries = set()
    for query in banned.get("banned_queries", []) if isinstance(banned, dict) else []:
        normalized = _normalize_query(query)
        if normalized:
            banned_queries.add(normalized)

    age_segment = get_age_segment(quiz.recipient_age, ruleset)
    segment_cfg = ruleset.get("age_segments", {}).get(age_segment, {})

    buckets: list[list[BucketItem]] = []

    base_queries = segment_cfg.get("base_queries", []) if isinstance(segment_cfg, dict) else []
    buckets.append(_collect_bucket(base_queries, "age_base", age_segment))

    if quiz.vibe and isinstance(segment_cfg, dict):
        vibes = segment_cfg.get("vibes", {})
        if isinstance(vibes, dict) and quiz.vibe in vibes:
            vibe_queries = vibes.get(quiz.vibe, {}).get("queries", [])
            buckets.append(_collect_bucket(vibe_queries, "vibe", f"{age_segment}.{quiz.vibe}"))
        else:
            buckets.append([])
    else:
        buckets.append([])

    if quiz.relationship:
        relationship_map = ruleset.get("relationship_map", {})
        relationship_queries = []
        if isinstance(relationship_map, dict):
            relationship_queries = relationship_map.get(quiz.relationship, {}).get("queries", [])
        buckets.append(_collect_bucket(relationship_queries, "relationship", f"relationship:{quiz.relationship}"))
    else:
        buckets.append([])

    if quiz.occasion:
        occasion_map = ruleset.get("occasion_map", {})
        occasion_queries = []
        if isinstance(occasion_map, dict):
            occasion_queries = occasion_map.get(quiz.occasion, {}).get("queries", [])
        buckets.append(_collect_bucket(occasion_queries, "occasion", f"occasion:{quiz.occasion}"))
    else:
        buckets.append([])

    interest_items: list[BucketItem] = []
    interests_map = ruleset.get("interests_map", {})
    if isinstance(interests_map, dict):
        for interest in quiz.interests:
            if interest in interests_map:
                queries = interests_map.get(interest, {}).get("queries", [])
                interest_items.extend(_collect_bucket(queries, "interests", f"interest:{interest}"))
    buckets.append(interest_items)

    keyword_items: list[BucketItem] = []
    description_map = ruleset.get("description_keywords_map", {})
    if quiz.interests_description and isinstance(description_map, dict):
        text = quiz.interests_description.lower()
        matched = 0
        for keyword, payload in description_map.items():
            if not isinstance(keyword, str):
                continue
            if keyword.lower() in text:
                queries = payload.get("queries", []) if isinstance(payload, dict) else []
                keyword_items.extend(_collect_bucket(queries, "description_keywords", f"keyword:{keyword}"))
                matched += 1
                if max_kw_from_desc and matched >= max_kw_from_desc:
                    break
    buckets.append(keyword_items)

    filtered: list[BucketItem] = []
    for bucket_items in buckets:
        if max_per_bucket:
            bucket_items = bucket_items[:max_per_bucket]
        filtered.append(bucket_items)

    seen: set[str] = set()
    results: list[BucketItem] = []
    for bucket_items in filtered:
        for item in bucket_items:
            query = item["query"]
            if query in banned_queries:
                continue
            if query in seen:
                continue
            results.append(item)
            seen.add(query)
            if max_total and len(results) >= max_total:
                return results

    if min_total and len(results) < min_total:
        return results

    return results
