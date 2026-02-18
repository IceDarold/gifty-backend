from __future__ import annotations

import os
import pytest

from app.db import get_session_context
from app.services.recommendation import RecommendationService
from app.services.embeddings import get_embedding_service
from recommendations.models import QuizAnswers

from .scenarios import get_scenarios


def _products_enabled() -> bool:
    return os.getenv("LLM_TEST_ENABLE_PRODUCTS") == "1"


@pytest.mark.ai_test
@pytest.mark.asyncio
@pytest.mark.skipif(not _products_enabled(), reason="LLM_TEST_ENABLE_PRODUCTS is not set")
@pytest.mark.parametrize("scenario", get_scenarios(), ids=lambda s: s.name)
async def test_llm_with_products(
    scenario,
    llm_reporter,
    timed_ai_service,
):
    llm_reporter.start_scenario(
        f"Products: {scenario.name}",
        {"quiz": scenario.quiz.model_dump()},
    )

    # 1) Generate hypotheses via LLM
    quiz_data = scenario.quiz.model_dump()
    topics = await timed_ai_service.normalize_topics(scenario.quiz.interests, language="ru")
    if not topics:
        llm_reporter.add_check("topics not empty", "fail")
        pytest.fail("LLM returned no topics")

    bulk = await timed_ai_service.generate_hypotheses_bulk(
        topics=topics,
        quiz_data=quiz_data,
        language="ru",
    )
    llm_reporter.add_output("bulk_hypotheses", bulk)

    # pick first hypothesis with search_queries
    selected = None
    for topic in topics:
        data = bulk.get(topic) or {}
        for h in data.get("hypotheses", []) or []:
            if h.get("search_queries"):
                selected = h
                break
        if selected:
            break

    if not selected:
        llm_reporter.add_check("has hypothesis with search_queries", "fail")
        pytest.fail("No hypothesis with search_queries from LLM")

    llm_reporter.add_check("has hypothesis with search_queries", "pass")

    # 2) Fetch products using RecommendationService
    async with get_session_context() as db:
        service = RecommendationService(db, get_embedding_service())
        previews = await service.find_preview_products(
            search_queries=selected.get("search_queries", []),
            hypothesis_title=selected.get("title", ""),
            max_price=scenario.quiz.budget,
        )

        llm_reporter.add_output(
            "preview_products",
            [
                {
                    "id": p.id,
                    "title": p.title,
                    "price": p.price,
                    "url": p.product_url,
                }
                for p in previews
            ],
        )

        if not previews:
            llm_reporter.add_check("preview products found", "warn", detail="empty preview list")
            pytest.skip("No preview products returned")

        llm_reporter.add_check("preview products found", "pass")

        deep = await service.get_deep_dive_products(
            search_queries=selected.get("search_queries", []),
            hypothesis_title=selected.get("title", ""),
            hypothesis_description=selected.get("description", ""),
            max_price=scenario.quiz.budget,
        )

        llm_reporter.add_output(
            "deep_dive_products",
            [
                {
                    "id": p.id,
                    "title": p.title,
                    "price": p.price,
                    "url": p.product_url,
                }
                for p in deep
            ],
        )

        llm_reporter.add_check(
            "deep dive products found",
            "pass" if deep else "warn",
            detail="empty deep dive list" if not deep else None,
        )
