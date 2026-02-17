# LLM Quality Report — 2026-02-17 14:40:12

## Summary
- Total scenarios: 1
- Pass: 0
- Warning: 1
- Fail: 0

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
- `normalize_topics`: 0.30s
- `generate_hypotheses_bulk`: 0.71s

**Outputs**
- llm_raw:normalize_topics
```json
[
  "Музыка"
]
```
- llm_raw:generate_hypotheses_bulk
```json
{
  "Музыка": {
    "is_wide": true,
    "question": "Какой аспект музыки ей наиболее интересен? Например, посещение концертов, коллекционирование виниловых пластинок или изучение истории музыки?",
    "branches": [
      "Виниловые пластинки",
      "Билеты на концерты",
      "Музыкальные инструменты",
      "История музыки"
    ]
  }
}
```
- session.topics
```json
[
  "Музыка"
]
```
- tracks.summary
```json
[
  {
    "topic": "Музыка",
    "status": "question",
    "hypotheses": [],
    "question": "Какой аспект музыки ей наиболее интересен? Например, посещение концертов, коллекционирование виниловых пластинок или изучение истории музыки?",
    "question_options": [
      "Виниловые пластинки",
      "Билеты на концерты",
      "Музыкальные инструменты",
      "История музыки"
    ]
  }
]
```

**Checks**
- [PASS] session has tracks or probe
- [PASS] hypotheses have titles
- [PASS] no duplicate hypothesis titles
- [WARN] RU language output

---
