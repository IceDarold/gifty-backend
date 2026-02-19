"""
Unit tests for prompt template formatting.

These tests ensure that every placeholder in a .md prompt file is correctly
provided by the calling code in AIReasoningService.

WHY: KeyError in str.format() is silent in mocked E2E tests but crashes in
production. This test file acts as a static contract between prompt files
and the service layer.

HOW: Each test formats the template with the exact parameters the real code
uses, then asserts no unfilled {placeholder} remains in the output.
"""
import json
import re
import pytest
from app.prompts import registry

# --- Helper ---

def has_unfilled_placeholders(text: str) -> bool:
    """
    Returns True if the text still contains any {placeholder} after formatting.
    Escaped {{ and }} are not counted.
    """
    # Remove escaped braces to avoid false positives from {{...}} in JSON examples
    cleaned = text.replace("{{", "").replace("}}", "")
    return bool(re.search(r"\{[a-zA-Z_]+\}", cleaned))


# --- Shared fixtures ---

SAMPLE_QUIZ_JSON = json.dumps({
    "relationship": "friend",
    "recipient_age": 30,
    "interests": ["coffee", "books"],
    "budget": 3000,
}, ensure_ascii=False, indent=2)

SAMPLE_TOPIC = "кофе"
SAMPLE_LANGUAGE = "ru"
SAMPLE_TOPICS_LIST = json.dumps(["кофе", "книги"], ensure_ascii=False)


# --- Tests ---

class TestSystemPrompt:
    def test_system_prompt_formats_correctly(self):
        template = registry.get_prompt("system")
        result = template.format(language=SAMPLE_LANGUAGE)
        assert not has_unfilled_placeholders(result), (
            "system.md has unfilled placeholders after formatting"
        )


class TestNormalizeTopics:
    def test_normalize_topics_formats_correctly(self):
        template = registry.get_prompt("normalize_topics")
        result = template.format(
            topics=json.dumps(["кофе", "книги"], ensure_ascii=False),
            language=SAMPLE_LANGUAGE,
        )
        assert not has_unfilled_placeholders(result), (
            "normalize_topics.md has unfilled placeholders after formatting"
        )


class TestClassifyTopic:
    def test_classify_topic_formats_correctly(self):
        template = registry.get_prompt("classify_topic")
        result = template.format(
            topic=SAMPLE_TOPIC,
            quiz_json=SAMPLE_QUIZ_JSON,
            language=SAMPLE_LANGUAGE,
        )
        assert not has_unfilled_placeholders(result), (
            "classify_topic.md has unfilled placeholders after formatting"
        )


class TestGenerateHypotheses:
    def test_generate_hypotheses_formats_correctly(self):
        template = registry.get_prompt("generate_hypotheses")
        result = template.format(
            topic=SAMPLE_TOPIC,
            quiz_json=SAMPLE_QUIZ_JSON,
            liked_concepts="None",
            disliked_concepts="None",
            shown_concepts="None",
        )
        assert not has_unfilled_placeholders(result), (
            "generate_hypotheses.md has unfilled placeholders after formatting"
        )

    def test_generate_hypotheses_with_concepts(self):
        template = registry.get_prompt("generate_hypotheses")
        result = template.format(
            topic=SAMPLE_TOPIC,
            quiz_json=SAMPLE_QUIZ_JSON,
            liked_concepts="книги, музыка",
            disliked_concepts="спорт",
            shown_concepts="кофемашина",
        )
        assert not has_unfilled_placeholders(result)


class TestGenerateHypothesesBulk:
    def test_bulk_formats_correctly(self):
        """This was the bug: 'topics' instead of 'topics_str' + missing 'language'."""
        template = registry.get_prompt("generate_hypotheses_bulk")
        result = template.format(
            topics_str=SAMPLE_TOPICS_LIST,
            quiz_json=SAMPLE_QUIZ_JSON,
            liked_concepts="None",
            disliked_concepts="None",
            language=SAMPLE_LANGUAGE,
        )
        assert not has_unfilled_placeholders(result), (
            "generate_hypotheses_bulk.md has unfilled placeholders after formatting.\n"
            "Expected: topics_str, quiz_json, liked_concepts, disliked_concepts, language"
        )

    def test_bulk_raises_on_wrong_key(self):
        """Regression: passing 'topics' instead of 'topics_str' must raise KeyError."""
        template = registry.get_prompt("generate_hypotheses_bulk")
        with pytest.raises(KeyError, match="topics_str"):
            template.format(
                topics=SAMPLE_TOPICS_LIST,   # Wrong key — intentionally
                quiz_json=SAMPLE_QUIZ_JSON,
                liked_concepts="None",
                disliked_concepts="None",
                language=SAMPLE_LANGUAGE,
            )

    def test_bulk_raises_without_language(self):
        """Regression: missing 'language' must raise KeyError."""
        template = registry.get_prompt("generate_hypotheses_bulk")
        with pytest.raises(KeyError, match="language"):
            template.format(
                topics_str=SAMPLE_TOPICS_LIST,
                quiz_json=SAMPLE_QUIZ_JSON,
                liked_concepts="None",
                disliked_concepts="None",
                # language= missing — intentionally
            )


class TestGenerateTopicHints:
    def test_topic_hints_formats_correctly(self):
        template = registry.get_prompt("generate_topic_hints")
        result = template.format(
            quiz_json=SAMPLE_QUIZ_JSON,
            topics_explored="кофе, книги",
        )
        assert not has_unfilled_placeholders(result), (
            "generate_topic_hints.md has unfilled placeholders after formatting"
        )

    def test_topic_hints_no_topics_explored(self):
        template = registry.get_prompt("generate_topic_hints")
        result = template.format(
            quiz_json=SAMPLE_QUIZ_JSON,
            topics_explored="None",
        )
        assert not has_unfilled_placeholders(result)


class TestPersonalizedProbes:
    def test_probe_exploration_formats_correctly(self):
        template = registry.get_prompt("personalized_probe_exploration")
        result = template.format(
            topic=SAMPLE_TOPIC,
            quiz_json=SAMPLE_QUIZ_JSON,
        )
        assert not has_unfilled_placeholders(result), (
            "personalized_probe_exploration.md has unfilled placeholders after formatting"
        )

    def test_probe_dead_end_formats_correctly(self):
        """dead_end prompt only needs quiz_json — topic is not used."""
        template = registry.get_prompt("personalized_probe_dead_end")
        result = template.format(
            topic="general",   # Extra param — Python ignores it, that's fine
            quiz_json=SAMPLE_QUIZ_JSON,
        )
        assert not has_unfilled_placeholders(result), (
            "personalized_probe_dead_end.md has unfilled placeholders after formatting"
        )
