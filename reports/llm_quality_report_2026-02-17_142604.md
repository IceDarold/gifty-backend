# LLM Quality Report — 2026-02-17 14:26:04

## Summary
- Total scenarios: 8
- Pass: 7
- Warning: 1
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
- `normalize_topics`: 1.68s
- `classify_topic`: 3.56s
- `classify_topic`: 1.87s
- `classify_topic`: 3.06s

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
[]
```
- llm_raw:classify_topic
```json
{
  "is_wide": false,
  "branches": null,
  "question": null,
  "refined_topic": "Кофе в контексте хобби Лего"
}
```
- llm_raw:classify_topic
```json
{
  "is_wide": true,
  "branches": [
    "Комфорт и удобство в поездках",
    "Приключения и активный отдых",
    "Планирование и организация путешествий",
    "Сохранение воспоминаний о путешествиях"
  ],
  "question": "Чтобы сузить тему 'Путешествия', не могли бы вы рассказать, что именно в них больше всего ценит получатель? Например, комфорт в дороге, новые впечатления, тщательное планирование или сохранение воспоминаний?",
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
- `normalize_topics`: 1.50s
- `classify_topic`: 3.17s

**Outputs**
- llm_raw:normalize_topics
```json
[
  "Музыка"
]
```
- llm_raw:classify_topic
```json
{
  "is_wide": true,
  "branches": [
    "Прослушивание музыки (наушники, винил, стриминг)",
    "Посещение концертов и музыкальных событий",
    "Создание музыки или игра на музыкальных инструментах",
    "Коллекционирование (винил, атрибутика, книги о музыке)"
  ],
  "question": "Чтобы подобрать идеальный подарок, расскажите, пожалуйста, что именно в музыке больше всего увлекает получателя: прослушивание, посещение концертов, создание музыки или коллекционирование?",
  "refined_topic": null
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
    "question": "Чтобы подобрать идеальный подарок, расскажите, пожалуйста, что именно в музыке больше всего увлекает получателя: прослушивание, посещение концертов, создание музыки или коллекционирование?",
    "question_options": [
      "Прослушивание музыки (наушники, винил, стриминг)",
      "Посещение концертов и музыкальных событий",
      "Создание музыки или игра на музыкальных инструментах",
      "Коллекционирование (винил, атрибутика, книги о музыке)"
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
- `normalize_topics`: 1.64s
- `classify_topic`: 3.28s

**Outputs**
- llm_raw:normalize_topics
```json
[
  "Виниловые проигрыватели 70-х"
]
```
- llm_raw:classify_topic
```json
{
  "is_wide": false,
  "branches": null,
  "question": null,
  "refined_topic": "Виниловые проигрыватели 70-х"
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

**LLM Timings**
- `normalize_topics`: 1.44s

**Outputs**
- llm_raw:normalize_topics
```json
[
  "Биохакинг",
  "Миксология",
  "Инди-игры"
]
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

**LLM Timings**
- `classify_topic`: 3.15s

**Outputs**
- llm_raw:classify_topic
```json
[
  "Слушание музыки (аудиофилия, стриминг)",
  "Игра на музыкальных инструментах",
  "Посещение концертов и музыкальных мероприятий",
  "Коллекционирование (виниловые пластинки, мерч)"
]
```
- classify_topic
```json
[
  "Слушание музыки (аудиофилия, стриминг)",
  "Игра на музыкальных инструментах",
  "Посещение концертов и музыкальных мероприятий",
  "Коллекционирование (виниловые пластинки, мерч)"
]
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
