# LLM Quality Report — 2026-02-17 14:24:54

## Summary
- Total scenarios: 8
- Pass: 8
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
- `normalize_topics`: 1.32s
- `classify_topic`: 3.38s
- `classify_topic`: 1.85s
- `classify_topic`: 3.36s

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
{}
```
- llm_raw:classify_topic
```json
{
  "is_wide": false,
  "branches": null,
  "question": null,
  "refined_topic": "Кофе, связанный с Лего"
}
```
- llm_raw:classify_topic
```json
{
  "is_wide": true,
  "branches": [
    "Активный отдых и приключения (походы, кемпинг, экстрим)",
    "Комфортные и расслабляющие поездки (спа, пляж, городские прогулки)",
    "Культурные и образовательные путешествия (музеи, гастрономия, изучение нового)",
    "Эффективная организация и удобство в поездках"
  ],
  "question": "Чтобы выбрать идеальный подарок, связанный с путешествиями, расскажите, пожалуйста, какой аспект путешествий больше всего увлекает получателя? Это может быть само приключение, комфорт в дороге, изучение новых культур или что-то другое?",
  "refined_topic": null
}
```

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
- `normalize_topics`: 1.15s
- `classify_topic`: 3.57s

**Outputs**
- llm_raw:normalize_topics
```json
[
  "Музыка"
]
```
- llm_raw:classify_topic
```json
{}
```

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

---

## Scenario: Interaction Persistence

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
  }
}
```

---
