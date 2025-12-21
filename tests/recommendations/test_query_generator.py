import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from recommendations.age_segment import get_age_segment
from recommendations.models import QuizAnswers
from recommendations.query_generator import generate_queries
from recommendations.query_rules_loader import load_ruleset


RULESET_PATH = ROOT / "config" / "gift_query_rules.v1.yaml"


def _get_queries(result):
    return [item["query"] for item in result]


def test_child_fun_queries_include_expected_items():
    ruleset = load_ruleset(str(RULESET_PATH))
    quiz = QuizAnswers(recipient_age=8, vibe="fun", relationship="child")

    result = generate_queries(quiz, ruleset)
    queries = _get_queries(result)

    assert "конструктор" in queries
    assert "машинка" in queries


def test_adult_cozy_queries_include_expected_items():
    ruleset = load_ruleset(str(RULESET_PATH))
    quiz = QuizAnswers(recipient_age=30, vibe="cozy")

    result = generate_queries(quiz, ruleset)
    queries = _get_queries(result)

    assert "плед" in queries
    assert "аромасвеча" in queries


def test_description_keywords_adds_queries():
    ruleset = load_ruleset(str(RULESET_PATH))
    quiz = QuizAnswers(recipient_age=30, interests_description="Любит кофе и чай")

    result = generate_queries(quiz, ruleset)
    queries = _get_queries(result)

    assert "кофемолка" in queries


def test_banned_queries_are_removed():
    ruleset = {
        "version": "v1",
        "limits": {
            "max_queries_total": 10,
            "max_queries_per_bucket": 5,
            "min_queries_total": 1,
            "max_keywords_from_description": 2,
        },
        "age_segments": {
            "adult": {"age_min": 30, "age_max": 40, "base_queries": ["плед", "книга"]}
        },
        "banned": {"banned_queries": ["плед"]},
    }

    quiz = QuizAnswers(recipient_age=30)
    result = generate_queries(quiz, ruleset)
    queries = _get_queries(result)

    assert "плед" not in queries
    assert "книга" in queries


def test_limits_are_applied_per_bucket_and_total():
    ruleset = {
        "version": "v1",
        "limits": {
            "max_queries_total": 3,
            "max_queries_per_bucket": 2,
            "min_queries_total": 1,
            "max_keywords_from_description": 2,
        },
        "age_segments": {
            "adult": {
                "age_min": 30,
                "age_max": 40,
                "base_queries": ["плед", "книга", "чайник"],
                "vibes": {"cozy": {"queries": ["аромасвеча", "диффузор", "ночник"]}},
            }
        },
        "banned": {"banned_queries": []},
    }

    quiz = QuizAnswers(recipient_age=30, vibe="cozy")
    result = generate_queries(quiz, ruleset)
    queries = _get_queries(result)

    assert len(queries) == 3
    assert queries == ["плед", "книга", "аромасвеча"]


def test_age_segment_selection():
    ruleset = {
        "age_segments": {"teen": {"age_min": 13, "age_max": 17}},
        "version": "v1",
        "limits": {},
    }
    assert get_age_segment(15, ruleset) == "teen"
