# LLM Quality Report — 2026-02-17 14:36:49

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
- `normalize_topics`: 0.41s
- `generate_hypotheses_bulk`: 2.91s

**Outputs**
- llm_raw:normalize_topics
```json
[
  "Лего",
  "Кофе",
  "Путешествия"
]
```
- llm_raw:generate_hypotheses_bulk
```json
{
  "Лего": {
    "is_wide": false,
    "hypotheses": [
      {
        "title": "Лего Стар Уорс: Коллекционная серия",
        "description": "Серия Лего Стар Уорс для поклонников фильма, включающая в себя коллекционные фигурки и модели",
        "primary_gap": "the_mirror",
        "reasoning": "Поскольку получатель интересуется Лего, эта коллекционная серия может быть отличным вариантом для выражения его интересов и любви к фильму",
        "search_queries": [
          "Лего Стар Уорс коллекционная серия",
          "Лего Стар Уорс фигурки",
          "Лего Стар Уорс модели"
        ]
      },
      {
        "title": "Лего Ideas: NASA Apollo Saturn V",
        "description": "Модель ракеты Saturn V от NASA, созданная из Лего, для поклонников космоса и истории",
        "primary_gap": "the_catalyst",
        "reasoning": "Эта модель может вдохновить получателя на изучение космоса и истории, а также развить его интерес к Лего",
        "search_queries": [
          "Лего Ideas NASA Apollo Saturn V",
          "Лего космос",
          "Лего история"
        ]
      },
      {
        "title": "Лего Креатив Бокс",
        "description": "Набор Лего для творческих людей, включающий в себя различные детали и элементы для построения",
        "primary_gap": "the_optimizer",
        "reasoning": "Этот набор может помочь получателю в его творческих занятиях и хобби, а также развить его навыки и想象ение",
        "search_queries": [
          "Лего Креатив Бокс",
          "Лего творческий набор",
          "Лего для взрослых"
        ]
      }
    ]
  },
  "Кофе": {
    "is_wide": false,
    "hypotheses": [
      {
        "title": "Кофемашина для дома",
        "description": "Кофемашина для приготовления кофе в домашних условиях, с различными функциями и возможностями",
        "primary_gap": "the_optimizer",
        "reasoning": "Поскольку получатель интересуется кофе, эта кофемашина может быть отличным вариантом для приготовления кофе дома и экономии времени",
        "search_queries": [
          "Кофемашина для дома",
          "Кофемашина автоматическая",
          "Кофемашина капсулы"
        ]
      },
      {
        "title": "Кофейный набор для путешествий",
        "description": "Набор для приготовления кофе в пути, включающий в себя различные аксессуары и инструменты",
        "primary_gap": "the_catalyst",
        "reasoning": "Этот набор может вдохновить получателя на путешествия и изучение новых мест, а также позволить ему наслаждаться кофе в дороге",
        "search_queries": [
          "Кофейный набор для путешествий",
          "Кофейный набор туристический",
          "Кофе для путешествий"
        ]
      },
      {
        "title": "Кофе из специального магазина",
        "description": "Кофе из специального магазина, с уникальными вкусами и ароматами",
        "primary_gap": "the_mirror",
        "reasoning": "Поскольку получатель интересуется кофе, этот кофе из специального магазина может быть отличным вариантом для выражения его индивидуальности и вкуса",
        "search_queries": [
          "Кофе из специального магазина",
          "Кофе гурман",
          "Кофе для кофеманов"
        ]
      }
    ]
  },
  "Путешествия": {
    "is_wide": true,
    "question": "Какой тип путешествий предпочитает получатель: пляжный отдых, городские туры или приключенческие путешествия?",
    "branches": [
      "Пляжный отдых",
      "Городские туры",
      "Приключенческие путешествия"
    ]
  }
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

**LLM Timings**
- `normalize_topics`: 0.47s

**Outputs**
- llm_raw:normalize_topics
```json
[
  "биохакинг",
  "миксология",
  "инди-игры"
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
