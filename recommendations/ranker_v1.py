from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Optional, Tuple

from integrations.takprodam.models import GiftCandidate
from pydantic import BaseModel

from .models import QuizAnswers


class RankingResult(BaseModel):
    engine_version: str = "ranker_v1"
    featured_gift: GiftCandidate
    gifts: list[GiftCandidate]
    debug: Optional[dict] = None


_NEGATIVE_KEYWORDS = ["18+", "эрот", "казино", "табак", "вейп"]

_VIBE_KEYWORDS = {
    "cozy": ["плед", "свеч", "ночник", "подушка", "диффузор", "уют"],
    "tech": ["наушник", "заряд", "гаджет", "колонк", "смарт", "powerbank"],
    "creative": ["рисован", "набор", "скетч", "хобби", "творч"],
    "fun": ["игра", "пазл", "юмор", "фан", "прикол"],
    "practical": ["органайзер", "термокружка", "бутылка", "полезн", "практич"],
    "wow": ["проектор", "умн", "вау", "квадрокоптер", "гироскутер"],
}

_GROUP_KEYWORDS = {
    "плед": "blanket",
    "свеч": "candle",
    "кружк": "mug",
    "набор": "kit",
    "игра": "game",
    "пазл": "puzzle",
    "диффузор": "diffuser",
    "ночник": "lamp",
    "подушка": "pillow",
}


@dataclass
class _ScoredCandidate:
    candidate: GiftCandidate
    score: float
    reasons: dict[str, Any]


def _tokenize(value: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9а-яё]+", value.lower())
    return [token for token in tokens if len(token) > 2]


def _collect_keywords(quiz: QuizAnswers) -> set[str]:
    keywords: set[str] = set()

    for interest in quiz.interests or []:
        if isinstance(interest, str):
            keywords.update(_tokenize(interest))

    for field in [quiz.vibe, quiz.relationship, quiz.occasion]:
        if isinstance(field, str):
            keywords.update(_tokenize(field))

    if quiz.interests_description:
        keywords.update(_tokenize(quiz.interests_description))

    return keywords


def score_candidate(quiz: QuizAnswers, c: GiftCandidate) -> Tuple[float, dict]:
    total_score = 0.0
    reasons: dict[str, Any] = {}

    title = (c.title or "").lower()
    description = (c.description or "").lower()

    keywords = _collect_keywords(quiz)
    title_matches: set[str] = set()
    desc_matches: set[str] = set()
    keyword_score = 0.0
    for kw in keywords:
        if kw in title:
            keyword_score += 2.0
            title_matches.add(kw)
        if kw in description:
            keyword_score += 1.0
            desc_matches.add(kw)
    if keyword_score:
        reasons["keywords"] = {
            "title_matches": sorted(title_matches),
            "description_matches": sorted(desc_matches),
            "score": keyword_score,
        }
    total_score += keyword_score
    if keywords and not keyword_score:
        total_score -= 1.0
        reasons["keyword_penalty"] = {"score": -1.0}

    budget_score = 0.0
    if quiz.budget and quiz.budget > 0:
        if c.price is not None:
            diff_ratio = abs(c.price - quiz.budget) / quiz.budget
            closeness = max(0.0, 1.0 - diff_ratio)
            budget_score = 2.5 * closeness
            if c.price < 0.7 * quiz.budget:
                budget_score -= 0.5
            elif c.price > 1.2 * quiz.budget:
                budget_score -= 0.5
        else:
            budget_score = -0.5
        reasons["budget_fit"] = {"price": c.price, "score": budget_score}
    total_score += budget_score

    vibe_score = 0.0
    if quiz.vibe:
        vibe_words = _VIBE_KEYWORDS.get(quiz.vibe.lower()) or []
        matched_vibe = [kw for kw in vibe_words if kw in title or kw in description]
        if matched_vibe:
            vibe_score = 3.0
            reasons["vibe"] = {"matched": matched_vibe, "score": vibe_score}
        total_score += vibe_score

    negative_penalty = 0.0
    if any(neg in title or neg in description for neg in _NEGATIVE_KEYWORDS):
        negative_penalty = -5.0
        reasons["negative"] = {"keywords": _NEGATIVE_KEYWORDS, "score": negative_penalty}
        total_score += negative_penalty

    if c.price is None and "budget_fit" not in reasons:
        reasons["price"] = {"missing": True}

    return total_score, reasons


def _apply_budget_filter(
    candidates: list[GiftCandidate], budget: Optional[int]
) -> tuple[list[GiftCandidate], dict[str, Any]]:
    debug: dict[str, Any] = {"applied_range": None, "initial": len(candidates)}
    if not budget or budget <= 0:
        debug["kept"] = len(candidates)
        return candidates, debug

    ranges = [1.2, 1.5]
    filtered_candidates: list[GiftCandidate] = []
    applied_range: tuple[float, float] | None = None

    for max_mult in ranges:
        filtered_candidates = [
            c
            for c in candidates
            if c.price is not None and c.price <= budget * max_mult
        ]
        applied_range = (0.0, max_mult)
        if len(filtered_candidates) >= 30:
            break

    if not filtered_candidates:
        filtered_candidates = candidates

    debug["applied_range"] = applied_range
    debug["kept"] = len(filtered_candidates)
    return filtered_candidates, debug


def _get_group_key(c: GiftCandidate) -> str:
    title = (c.title or "").lower()
    for needle, group in _GROUP_KEYWORDS.items():
        if needle in title:
            return group
    if c.category:
        return c.category.lower()
    tokens = _tokenize(title)
    generic = {"товар", "подарок", "набор", "комплект", "аксессуар"}
    for token in tokens:
        if token not in generic:
            return token
    return "other"


def _select_diverse_candidates(
    scored: list[_ScoredCandidate], top_n: int
) -> tuple[list[_ScoredCandidate], dict[str, Any]]:
    def _pass_select(
        items: list[_ScoredCandidate],
        group_limit: int,
        category_limit: int,
        selected: list[_ScoredCandidate],
        group_counts: dict[str, int],
        category_counts: dict[str, int],
        skipped: list[dict[str, Any]],
    ) -> None:
        for item in items:
            if item in selected:
                continue
            group = _get_group_key(item.candidate)
            category = (item.candidate.category or "other").lower()

            if group != "other" and group_counts[group] >= group_limit:
                skipped.append({"gift_id": item.candidate.gift_id, "reason": "group_limit", "group": group})
                continue
            if category != "other" and category_counts[category] >= category_limit:
                skipped.append(
                    {"gift_id": item.candidate.gift_id, "reason": "category_limit", "category": category}
                )
                continue

            selected.append(item)
            group_counts[group] += 1
            category_counts[category] += 1
            if len(selected) >= top_n:
                break

    group_counts: dict[str, int] = defaultdict(int)
    category_counts: dict[str, int] = defaultdict(int)
    selected: list[_ScoredCandidate] = []
    skipped: list[dict[str, Any]] = []

    _pass_select(scored, 2, 3, selected, group_counts, category_counts, skipped)

    added_fallback = 0
    if len(selected) < top_n:
        before = len(selected)
        _pass_select(scored, 4, 5, selected, group_counts, category_counts, skipped)
        added_fallback = len(selected) - before

    if len(selected) < top_n:
        for item in scored:
            if item in selected:
                continue
            selected.append(item)
            if len(selected) >= top_n:
                break

    debug = {
        "group_counts": dict(group_counts),
        "category_counts": dict(category_counts),
        "skipped": skipped,
        "removed_by_diversity": len(skipped),
        "added_by_fallback": added_fallback,
    }
    return selected, debug


def rank_candidates(
    quiz: QuizAnswers,
    candidates: list[GiftCandidate],
    *,
    top_n: int = 10,
    debug: bool = False,
) -> RankingResult:
    filtered = [c for c in candidates if c.title and c.product_url]
    budget_filtered, budget_debug = _apply_budget_filter(filtered, quiz.budget)

    scored: list[_ScoredCandidate] = []
    for candidate in budget_filtered:
        score, reasons = score_candidate(quiz, candidate)
        scored.append(_ScoredCandidate(candidate=candidate, score=score, reasons=reasons))

    scored.sort(key=lambda item: item.score, reverse=True)
    top_scored, diversity_debug = _select_diverse_candidates(scored, top_n)

    if not top_scored:
        raise ValueError("No candidates to rank")

    selected_candidates = top_scored
    if len(selected_candidates) > 1:
        first, second = selected_candidates[0], selected_candidates[1]
        if first.candidate.price is None and second.candidate.price is not None:
            selected_candidates = [second, first] + selected_candidates[2:]

    gifts = [item.candidate for item in selected_candidates]
    featured = gifts[0]

    debug_info = None
    if debug:
        debug_info = {
            "applied_budget_range": budget_debug.get("applied_range"),
            "candidates_in": len(candidates),
            "candidates_after_filter": len(budget_filtered),
            "requested_top_n": top_n,
            "returned_count": len(gifts),
            "scored_top20": [
                {
                    "gift_id": item.candidate.gift_id,
                    "score": item.score,
                    "reasons": item.reasons,
                    "title": item.candidate.title,
                    "price": item.candidate.price,
                }
                for item in scored[:20]
            ],
            "diversity": diversity_debug,
        }

    return RankingResult(featured_gift=featured, gifts=gifts, debug=debug_info)
