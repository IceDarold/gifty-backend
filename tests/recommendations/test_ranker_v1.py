from __future__ import annotations

from integrations.takprodam.models import GiftCandidate
from recommendations.models import QuizAnswers
from recommendations.ranker_v1 import RankingResult, rank_candidates


def _make_candidate(
    gift_id: str,
    title: str,
    *,
    description: str | None = None,
    price: float | None = None,
    category: str | None = None,
) -> GiftCandidate:
    return GiftCandidate(
        gift_id=gift_id,
        title=title,
        description=description,
        price=price,
        currency="RUB",
        image_url=None,
        product_url=f"https://example.com/{gift_id}",
        merchant="test",
        category=category,
        raw={},
    )


def test_cozy_vibe_prioritizes_cozy_items():
    quiz = QuizAnswers(recipient_age=25, vibe="cozy", budget=2000)
    candidates = [
        _make_candidate("blanket1", "Тёплый плед", description="мягкий плед", price=1800),
        _make_candidate("candle1", "Ароматическая свеча", price=900),
        _make_candidate("tech1", "Беспроводная колонка", price=1900),
        _make_candidate("game1", "Настольная игра", price=1500),
    ]

    result = rank_candidates(quiz, candidates, top_n=4)

    assert {result.gift_ids[0], result.gift_ids[1]} == {"blanket1", "candle1"}


def test_budget_filter_excludes_too_expensive():
    quiz = QuizAnswers(recipient_age=30, budget=100)
    affordable = [
        _make_candidate(f"affordable-{idx}", f"Доступный подарок {idx}", price=90)
        for idx in range(35)
    ]
    expensive = _make_candidate("expensive", "Дорогой подарок", price=500)
    candidates = affordable + [expensive]

    result = rank_candidates(quiz, candidates, top_n=10)

    assert "expensive" not in result.gift_ids
    assert len(result.gift_ids) == 10


def test_diversity_limits_group_duplicates():
    quiz = QuizAnswers(recipient_age=30, budget=1500)
    candidates = [
        _make_candidate(f"blanket-{i}", f"Плед уютный {i}", price=1000)
        for i in range(5)
    ]
    candidates.extend([
        _make_candidate("game", "Настольная игра", price=1200),
        _make_candidate("mug", "Керамическая кружка", price=800),
    ])

    result = rank_candidates(quiz, candidates, top_n=4)

    blanket_count = sum(1 for gid in result.gift_ids if gid.startswith("blanket-"))
    assert blanket_count <= 2


def test_featured_is_first_item():
    quiz = QuizAnswers(recipient_age=20, budget=500)
    candidates = [
        _make_candidate("first", "Плед уютный", price=400),
        _make_candidate("second", "Настольная игра", price=300),
    ]

    result = rank_candidates(quiz, candidates, top_n=2)

    assert result.featured_gift_id == result.gift_ids[0]
    assert set(result.gift_ids) == {"first", "second"}


def test_handles_missing_price():
    quiz = QuizAnswers(recipient_age=20)
    candidates = [
        _make_candidate("no-price", "Подарок без цены", price=None),
        _make_candidate("with-price", "Подарок с ценой", price=500),
    ]

    result = rank_candidates(quiz, candidates, top_n=2)

    assert isinstance(result, RankingResult)
    assert len(result.gift_ids) == 2
