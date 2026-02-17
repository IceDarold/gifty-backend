# LLM Quality Report — 2026-02-17 14:43:53

## Summary
- Total scenarios: 1
- Pass: 1
- Warning: 0
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
- `normalize_topics`: 1.86s
- `classify_topic`: 1.13s

**Outputs**
- llm_raw:normalize_topics
```json
[
  "Лего",
  "Кофе",
  "Путешествия"
]
```
- llm_raw:classify_topic
```json
{
  "is_wide": false,
  "branches": [],
  "question": null,
  "refined_topic": "Лего, связанное с путешествиями, или Лего, которое можно собирать, попивая кофе"
}
```

---
