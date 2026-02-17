# LLM Quality Report — 2026-02-14 19:54:21

## Summary
- Total scenarios: 7
- Pass: 0
- Warning: 7
- Fail: 0

---

## Scenario: Init Session: Lego + Coffee + Travel

**Input**
```json
{
  "quiz": {
    "relationship": null,
    "gifting_goal": null,
    "effort_level": "low",
    "session_mode": "thoughtful",
    "budget": null,
    "deadline_days": null,
    "language": "ru",
    "recipient_age": 28,
    "recipient_gender": "male",
    "occasion": null,
    "vibe": null,
    "interests": [
      "Лего и кофе",
      "Путешествия"
    ],
    "interests_description": null
  }
}
```

**LLM Timings**
- `normalize_topics`: 1.38s — connection error: Connection error.

**Checks**
- [WARN] LLM call succeeded: normalize_topics — connection error

**Reviewer Notes**
- Skipped due to LLM connection error in normalize_topics: Connection error.

---

## Scenario: Init Session: Wide Topic: Music

**Input**
```json
{
  "quiz": {
    "relationship": null,
    "gifting_goal": null,
    "effort_level": "low",
    "session_mode": "thoughtful",
    "budget": null,
    "deadline_days": null,
    "language": "ru",
    "recipient_age": 35,
    "recipient_gender": "female",
    "occasion": null,
    "vibe": null,
    "interests": [
      "Музыка"
    ],
    "interests_description": null
  }
}
```

**LLM Timings**
- `normalize_topics`: 1.27s — connection error: Connection error.

**Checks**
- [WARN] LLM call succeeded: normalize_topics — connection error

**Reviewer Notes**
- Skipped due to LLM connection error in normalize_topics: Connection error.

---

## Scenario: Init Session: Narrow Topic: Vinyl 70s

**Input**
```json
{
  "quiz": {
    "relationship": null,
    "gifting_goal": null,
    "effort_level": "low",
    "session_mode": "thoughtful",
    "budget": null,
    "deadline_days": null,
    "language": "ru",
    "recipient_age": 42,
    "recipient_gender": "male",
    "occasion": null,
    "vibe": null,
    "interests": [
      "Виниловые проигрыватели 70-х"
    ],
    "interests_description": null
  }
}
```

**LLM Timings**
- `normalize_topics`: 1.42s — connection error: Connection error.

**Checks**
- [WARN] LLM call succeeded: normalize_topics — connection error

**Reviewer Notes**
- Skipped due to LLM connection error in normalize_topics: Connection error.

---

## Scenario: Init Session: Complex Mix

**Input**
```json
{
  "quiz": {
    "relationship": null,
    "gifting_goal": null,
    "effort_level": "low",
    "session_mode": "thoughtful",
    "budget": null,
    "deadline_days": null,
    "language": "ru",
    "recipient_age": 30,
    "recipient_gender": "female",
    "occasion": null,
    "vibe": null,
    "interests": [
      "биохакинг",
      "миксология",
      "инди-игры"
    ],
    "interests_description": null
  }
}
```

**LLM Timings**
- `normalize_topics`: 1.21s — connection error: Connection error.

**Checks**
- [WARN] LLM call succeeded: normalize_topics — connection error

**Reviewer Notes**
- Skipped due to LLM connection error in normalize_topics: Connection error.

---

## Scenario: Classify Topic: Music

**Input**
```json
{
  "topic": "Музыка",
  "quiz": {
    "relationship": null,
    "gifting_goal": null,
    "effort_level": "low",
    "session_mode": "thoughtful",
    "budget": null,
    "deadline_days": null,
    "language": "ru",
    "recipient_age": 30,
    "recipient_gender": null,
    "occasion": null,
    "vibe": null,
    "interests": [
      "Музыка"
    ],
    "interests_description": null
  }
}
```

**LLM Timings**
- `classify_topic`: 1.29s — connection error: Connection error.

**Checks**
- [WARN] LLM call succeeded: classify_topic — connection error

**Reviewer Notes**
- Skipped due to LLM connection error in classify_topic: Connection error.

---

## Scenario: Personalized Probe: dead_end

**Input**
```json
{
  "context_type": "dead_end",
  "quiz": {
    "relationship": null,
    "gifting_goal": null,
    "effort_level": "low",
    "session_mode": "thoughtful",
    "budget": null,
    "deadline_days": null,
    "language": "ru",
    "recipient_age": 45,
    "recipient_gender": null,
    "occasion": null,
    "vibe": null,
    "interests": [
      "Винил"
    ],
    "interests_description": null
  }
}
```

**LLM Timings**
- `generate_personalized_probe:dead_end`: 1.23s — connection error: Connection error.

**Checks**
- [WARN] LLM call succeeded: generate_personalized_probe:dead_end — connection error

**Reviewer Notes**
- Skipped due to LLM connection error in generate_personalized_probe:dead_end: Connection error.

---

## Scenario: Topic Hints

**Input**
```json
{
  "quiz": {
    "relationship": null,
    "gifting_goal": null,
    "effort_level": "low",
    "session_mode": "thoughtful",
    "budget": null,
    "deadline_days": null,
    "language": "ru",
    "recipient_age": 28,
    "recipient_gender": null,
    "occasion": null,
    "vibe": null,
    "interests": [
      "Кофе"
    ],
    "interests_description": null
  },
  "topics_explored": [
    "Кофе"
  ]
}
```

**LLM Timings**
- `generate_topic_hints`: 1.47s — connection error: Connection error.

**Checks**
- [WARN] LLM call succeeded: generate_topic_hints — connection error

**Reviewer Notes**
- Skipped due to LLM connection error in generate_topic_hints: Connection error.

---
