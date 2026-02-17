# LLM Quality Report — 2026-02-17 14:36:39

## Summary
- Total scenarios: 1
- Pass: 1
- Warning: 0
- Fail: 0

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
- `classify_topic`: 0.63s

**Outputs**
- llm_raw:classify_topic
```json
{
  "is_wide": true,
  "branches": [
    "Инструменты для музыки",
    "Музыкальные альбомы",
    "Концертные билеты",
    "Музыкальное оборудование"
  ],
  "question": "Какой аспект музыки интересует получателя больше всего: исполнение, прослушивание или создание?",
  "refined_topic": null
}
```
- classify_topic
```json
{
  "is_wide": true,
  "branches": [
    "Инструменты для музыки",
    "Музыкальные альбомы",
    "Концертные билеты",
    "Музыкальное оборудование"
  ],
  "question": "Какой аспект музыки интересует получателя больше всего: исполнение, прослушивание или создание?",
  "refined_topic": null
}
```

**Checks**
- [PASS] is_wide present
- [PASS] wide topic likely
- [PASS] wide topic has question
- [PASS] wide topic has branches

---
