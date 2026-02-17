# LLM Quality Report — 2026-02-17 14:24:16

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
- `classify_topic`: 3.37s

**Outputs**
- llm_raw:classify_topic
```json
{
  "is_wide": true,
  "branches": [
    "Активное прослушивание (оборудование, форматы)",
    "Создание музыки (инструменты, программы)",
    "Посещение мероприятий (концерты, фестивали)",
    "Коллекционирование и изучение (винилы, биографии, история)"
  ],
  "question": "Чтобы помочь мне найти идеальный подарок, расскажите, пожалуйста, что именно в музыке увлекает этого человека больше всего? Он(а) любит слушать музыку в высоком качестве, создавать её, ходить на концерты или коллекционировать что-то связанное с ней?",
  "refined_topic": null
}
```
- classify_topic
```json
{
  "is_wide": true,
  "branches": [
    "Активное прослушивание (оборудование, форматы)",
    "Создание музыки (инструменты, программы)",
    "Посещение мероприятий (концерты, фестивали)",
    "Коллекционирование и изучение (винилы, биографии, история)"
  ],
  "question": "Чтобы помочь мне найти идеальный подарок, расскажите, пожалуйста, что именно в музыке увлекает этого человека больше всего? Он(а) любит слушать музыку в высоком качестве, создавать её, ходить на концерты или коллекционировать что-то связанное с ней?",
  "refined_topic": null
}
```

**Checks**
- [PASS] is_wide present
- [PASS] wide topic likely
- [PASS] wide topic has question
- [PASS] wide topic has branches

---
