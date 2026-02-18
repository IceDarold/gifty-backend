from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List

from recommendations.models import QuizAnswers, Language


@dataclass(frozen=True)
class Scenario:
    name: str
    quiz: QuizAnswers


def _limit_items(items: List[Scenario]) -> List[Scenario]:
    raw = os.getenv("LLM_TEST_LIMIT")
    if raw is None or raw == "":
        return items
    try:
        limit = int(raw)
    except ValueError:
        return items
    if limit <= 0:
        return items
    return items[:limit]


def get_scenarios() -> List[Scenario]:
    scenarios = [
        Scenario(
            name="Lego + Coffee + Travel",
            quiz=QuizAnswers(
                interests=["Лего и кофе", "Путешествия"],
                recipient_age=28,
                recipient_gender="male",
                language=Language.RU,
            ),
        ),
        Scenario(
            name="Wide Topic: Music",
            quiz=QuizAnswers(
                interests=["Музыка"],
                recipient_age=35,
                recipient_gender="female",
                language=Language.RU,
            ),
        ),
        Scenario(
            name="Narrow Topic: Vinyl 70s",
            quiz=QuizAnswers(
                interests=["Виниловые проигрыватели 70-х"],
                recipient_age=42,
                recipient_gender="male",
                language=Language.RU,
            ),
        ),
        Scenario(
            name="Complex Mix",
            quiz=QuizAnswers(
                interests=["биохакинг", "миксология", "инди-игры"],
                recipient_age=30,
                recipient_gender="female",
                language=Language.RU,
            ),
        ),
    ]
    return _limit_items(scenarios)
