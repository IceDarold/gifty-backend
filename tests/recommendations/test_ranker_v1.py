import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from integrations.takprodam.models import GiftCandidate
from recommendations.models import QuizAnswers
from recommendations.ranker_v1 import rank_candidates


def _make_candidate(gift_id: str, title: str, price: float | None = None, category: str | None = None):
    return GiftCandidate(
        gift_id=gift_id,
        title=title,
        description="",
        price=price,
        currency="RUB",
        image_url=None,
        product_url="https://example.com/item",
        merchant=None,
        category=category,
        raw={},
    )


def test_relevance_prefers_cozy_and_coffee():
    quiz = QuizAnswers(recipient_age=30, vibe="cozy", interests=["coffee"], budget=6000)

    candidates = [
        _make_candidate("takprodam:1", "Плед уютный", 5500, category="home"),
        _make_candidate("takprodam:2", "Кофемолка ручная", 5200, category="kitchen"),
        _make_candidate("takprodam:3", "Ювелирное кольцо", 5800, category="jewelry"),
    ]

    result = rank_candidates(quiz, candidates, debug=True)

    assert result.gifts[0].gift_id in {"takprodam:1", "takprodam:2"}
    assert result.debug is not None
    assert result.debug.get("applied_budget_range") is not None


def test_diversity_fallback_fills_top_n():
    quiz = QuizAnswers(recipient_age=30, vibe="cozy")

    candidates = [
        _make_candidate(f"takprodam:{idx}", "Плед уютный", 1000, category="home")
        for idx in range(12)
    ]

    result = rank_candidates(quiz, candidates, top_n=10, debug=True)

    assert len(result.gifts) == 10
    assert result.debug is not None
    diversity = result.debug.get("diversity", {})
    assert diversity.get("added_by_fallback", 0) >= 0


def test_ranker_returns_objects_variant_a():
    quiz = QuizAnswers(recipient_age=30, vibe="cozy")
    candidates = [
        _make_candidate("takprodam:1", "Плед уютный", 1000),
        _make_candidate("takprodam:2", "Свеча ароматическая", 1200),
    ]

    result = rank_candidates(quiz, candidates, top_n=2, debug=True)

    assert result.featured_gift.gift_id == result.gifts[0].gift_id
    assert len(result.gifts) == 2
