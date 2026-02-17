# LLM Quality Report — 2026-02-17 14:45:21

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
- `normalize_topics`: 0.44s
- `generate_hypotheses_bulk`: 2.66s

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
        "title": "Лего набор для взрослых",
        "description": "Лего набор, предназначенный для взрослых, который позволяет реализовать творчество и расслабиться",
        "primary_gap": "the_mirror",
        "reasoning": "Поскольку интересы получателя включают Лего, этот подарок будет соответствовать его вкусу и интересам",
        "search_queries": [
          "Лего наборы для взрослых",
          "Лего творчество"
        ]
      },
      {
        "title": "Лего организатор",
        "description": "Органайзер для Лего деталей, который помогает сохранить порядок и упростить процесс поиска необходимых деталей",
        "primary_gap": "the_optimizer",
        "reasoning": "Этот подарок будет полезен для упрощения процесса работы с Лего и сохранения порядка",
        "search_queries": [
          "Лего организатор",
          "Лего хранилище"
        ]
      },
      {
        "title": "Книга о истории Лего",
        "description": "Книга, рассказывающая об истории и эволюции Лего, которая может быть интересна получателю",
        "primary_gap": "the_catalyst",
        "reasoning": "Эта книга может быть интересна получателю, если он хочет узнать больше о истории и развитии Лего",
        "search_queries": [
          "Книга об истории Лего",
          "Лего энциклопедия"
        ]
      }
    ]
  },
  "Кофе": {
    "is_wide": false,
    "hypotheses": [
      {
        "title": "Кофемашина",
        "description": "Кофемашина, которая позволяет приготовить кофе дома, что может быть полезно для получателя",
        "primary_gap": "the_optimizer",
        "reasoning": "Этот подарок будет полезен для упрощения процесса приготовления кофе и сохранения времени",
        "search_queries": [
          "Кофемашина",
          "Кофеварка"
        ]
      },
      {
        "title": "Кофейный набор",
        "description": "Набор кофе разных сортов и вкусов, который позволяет попробовать новые виды кофе",
        "primary_gap": "the_catalyst",
        "reasoning": "Этот подарок может быть интересен получателю, если он хочет попробовать новые виды кофе и расширить свои вкусовые предпочтения",
        "search_queries": [
          "Кофейный набор",
          "Кофе разных сортов"
        ]
      },
      {
        "title": "Кофейная чашка",
        "description": "Кофейная чашка, которая может быть персонализирована с именем или сообщением, что может быть приятным подарком",
        "primary_gap": "the_mirror",
        "reasoning": "Этот подарок будет соответствовать вкусу и интересам получателя, если он любит кофе и ценит персонализированные вещи",
        "search_queries": [
          "Кофейная чашка",
          "Персонализированная кофейная чашка"
        ]
      }
    ]
  },
  "Путешествия": {
    "is_wide": true,
    "branches": [
      "Отдых на пляже",
      "Горные путешествия",
      "Городские туры"
    ],
    "question": "Какой тип путешествий предпочитает получатель?"
  }
}
```
- session.topics
```json
[
  "Лего",
  "Кофе",
  "Путешествия"
]
```
- tracks.summary
```json
[
  {
    "topic": "Лего",
    "status": "ready",
    "hypotheses": [
      "Лего набор для взрослых",
      "Лего организатор",
      "Книга о истории Лего"
    ],
    "question": null,
    "question_options": []
  },
  {
    "topic": "Кофе",
    "status": "ready",
    "hypotheses": [
      "Кофемашина",
      "Кофейный набор",
      "Кофейная чашка"
    ],
    "question": null,
    "question_options": []
  },
  {
    "topic": "Путешествия",
    "status": "question",
    "hypotheses": [],
    "question": "Какой тип путешествий предпочитает получатель?",
    "question_options": [
      "Отдых на пляже",
      "Горные путешествия",
      "Городские туры"
    ]
  }
]
```

**Checks**
- [PASS] session has tracks or probe
- [PASS] hypotheses have titles
- [PASS] no duplicate hypothesis titles
- [PASS] RU language output
- [PASS] recipient persisted
- [PASS] hypotheses persisted — db=6, expected>=6

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
- `normalize_topics`: 0.47s
- `generate_hypotheses_bulk`: 0.82s

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
    "question": "Какая область музыки больше всего интересует получателя? Например, посещение концертов, коллекционирование виниловых пластинок или игра на музыкальных инструментах?",
    "branches": [
      "Виниловые пластинки",
      "Билеты на концерты",
      "Музыкальные инструменты",
      "Аудиооборудование"
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
    "question": "Какая область музыки больше всего интересует получателя? Например, посещение концертов, коллекционирование виниловых пластинок или игра на музыкальных инструментах?",
    "question_options": [
      "Виниловые пластинки",
      "Билеты на концерты",
      "Музыкальные инструменты",
      "Аудиооборудование"
    ]
  }
]
```

**Checks**
- [PASS] session has tracks or probe
- [PASS] hypotheses have titles
- [PASS] no duplicate hypothesis titles
- [WARN] RU language output
- [PASS] recipient persisted
- [WARN] hypotheses persisted — no ready hypotheses to persist

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
- `normalize_topics`: 0.39s
- `generate_hypotheses_bulk`: 1.67s

**Outputs**
- llm_raw:normalize_topics
```json
[
  "Виниловые проигрыватели"
]
```
- llm_raw:generate_hypotheses_bulk
```json
{
  "Виниловые проигрыватели": {
    "is_wide": false,
    "hypotheses": [
      {
        "title": "Виниловая пластинка редкого исполнителя 70-х",
        "description": "Подарок, который позволит ему дополнить свою коллекцию и насладиться музыкой его любимого артиста",
        "primary_gap": "the_mirror",
        "reasoning": "Поскольку у него есть интерес к виниловым проигрывателям 70-х, этот подарок поможет ему чувствовать себя связанным со своей эпохой и музыкой",
        "search_queries": [
          "редкие виниловые пластинки 70-х",
          "виниловые пластинки классического рока"
        ]
      },
      {
        "title": "Устройство для очистки виниловых пластинок",
        "description": "Практичный подарок, который поможет ему поддерживать свою коллекцию в идеальном состоянии",
        "primary_gap": "the_optimizer",
        "reasoning": "Этот подарок сделает его жизнь проще, позволяя ему наслаждаться музыкой без забот о состоянии своих пластинок",
        "search_queries": [
          "устройство для очистки виниловых пластинок",
          "чистящее средство для винила"
        ]
      },
      {
        "title": "Книга об истории виниловых проигрывателей",
        "description": "Подарок, который расширит его знания и понимание музыкальной индустрии",
        "primary_gap": "the_catalyst",
        "reasoning": "Эта книга поможет ему глубже понять историю и развитие виниловых проигрывателей, что может вдохновить его на новые открытия",
        "search_queries": [
          "книги об истории виниловых проигрывателей",
          "история музыкальной индустрии"
        ]
      }
    ]
  }
}
```
- session.topics
```json
[
  "Виниловые проигрыватели"
]
```
- tracks.summary
```json
[
  {
    "topic": "Виниловые проигрыватели",
    "status": "ready",
    "hypotheses": [
      "Виниловая пластинка редкого исполнителя 70-х",
      "Устройство для очистки виниловых пластинок",
      "Книга об истории виниловых проигрывателей"
    ],
    "question": null,
    "question_options": []
  }
]
```

**Checks**
- [PASS] session has tracks or probe
- [PASS] hypotheses have titles
- [PASS] no duplicate hypothesis titles
- [PASS] RU language output
- [PASS] recipient persisted
- [PASS] hypotheses persisted — db=3, expected>=3

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
- `normalize_topics`: 0.45s
- `generate_hypotheses_bulk`: 2.87s

**Outputs**
- llm_raw:normalize_topics
```json
[
  "биохакинг",
  "миксология",
  "инди-игры"
]
```
- llm_raw:generate_hypotheses_bulk
```json
{
  "биохакинг": {
    "is_wide": false,
    "hypotheses": [
      {
        "title": "Курс по биохакингу и оптимизации здоровья",
        "description": "Онлайн-курс, который поможет получателю узнать больше о биохакинге и применить полученные знания на практике",
        "primary_gap": "the_catalyst",
        "reasoning": "Получатель интересуется биохакингом, но может не иметь достаточного опыта или знаний, чтобы начать применять его на практике. Этот курс поможет ему получить необходимые знания и навыки",
        "search_queries": [
          "курсы биохакинга",
          "биохакинг для начинающих",
          "онлайн-курсы здоровья"
        ]
      },
      {
        "title": "Набор для измерения биометрических показателей",
        "description": "Набор устройств для измерения различных биометрических показателей, таких как частота сердечных сокращений, артериальное давление и т.д.",
        "primary_gap": "the_optimizer",
        "reasoning": "Получатель интересуется биохакингом и может хотеть иметь возможность измерять свои биометрические показатели, чтобы оптимизировать свое здоровье",
        "search_queries": [
          "биометрические устройства",
          "измерение частоты сердечных сокращений",
          "артериальное давление монитор"
        ]
      },
      {
        "title": "Книга о биохакинге и самооптимизации",
        "description": "Книга, которая рассказывает о биохакинге и самооптимизации, и предоставляет практические советы и рекомендации",
        "primary_gap": "the_mirror",
        "reasoning": "Получатель интересуется биохакингом и может хотеть иметь возможность узнать больше о нем и о том, как он может применить его на практике",
        "search_queries": [
          "книги о биохакинге",
          "биохакинг и самооптимизация",
          "книги о здоровье"
        ]
      }
    ]
  },
  "миксология": {
    "is_wide": false,
    "hypotheses": [
      {
        "title": "Набор для создания коктейлей",
        "description": "Набор ингредиентов и инструментов для создания различных коктейлей",
        "primary_gap": "the_catalyst",
        "reasoning": "Получатель интересуется миксологией и может хотеть иметь возможность создавать свои собственные коктейли",
        "search_queries": [
          "наборы для коктейлей",
          "миксологические наборы",
          "коктейльные ингредиенты"
        ]
      },
      {
        "title": "Книга о миксологии и коктейлях",
        "description": "Книга, которая рассказывает о миксологии и коктейлях, и предоставляет рецепты и советы",
        "primary_gap": "the_mirror",
        "reasoning": "Получатель интересуется миксологией и может хотеть иметь возможность узнать больше о ней и о том, как создавать коктейли",
        "search_queries": [
          "книги о миксологии",
          "коктейльные рецепты",
          "миксологические книги"
        ]
      },
      {
        "title": "Курс по миксологии и барменству",
        "description": "Онлайн-курс, который поможет получателю узнать больше о миксологии и барменстве и применить полученные знания на практике",
        "primary_gap": "the_catalyst",
        "reasoning": "Получатель интересуется миксологией и может хотеть иметь возможность получить профессиональные знания и навыки",
        "search_queries": [
          "курсы миксологии",
          "барменские курсы",
          "онлайн-курсы миксологии"
        ]
      }
    ]
  },
  "инди-игры": {
    "is_wide": true,
    "question": "Какой тип инди-игр предпочитает получатель?",
    "branches": [
      "приключенческие игры",
      "стратегические игры",
      "игры с сильной историей"
    ]
  }
}
```
- session.topics
```json
[
  "биохакинг",
  "миксология",
  "инди-игры"
]
```
- tracks.summary
```json
[
  {
    "topic": "биохакинг",
    "status": "ready",
    "hypotheses": [
      "Курс по биохакингу и оптимизации здоровья",
      "Набор для измерения биометрических показателей",
      "Книга о биохакинге и самооптимизации"
    ],
    "question": null,
    "question_options": []
  },
  {
    "topic": "миксология",
    "status": "ready",
    "hypotheses": [
      "Набор для создания коктейлей",
      "Книга о миксологии и коктейлях",
      "Курс по миксологии и барменству"
    ],
    "question": null,
    "question_options": []
  },
  {
    "topic": "инди-игры",
    "status": "question",
    "hypotheses": [],
    "question": "Какой тип инди-игр предпочитает получатель?",
    "question_options": [
      "приключенческие игры",
      "стратегические игры",
      "игры с сильной историей"
    ]
  }
]
```

**Checks**
- [PASS] session has tracks or probe
- [PASS] hypotheses have titles
- [PASS] no duplicate hypothesis titles
- [PASS] RU language output
- [PASS] recipient persisted
- [PASS] hypotheses persisted — db=6, expected>=6

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
- `classify_topic`: 0.58s

**Outputs**
- llm_raw:classify_topic
```json
{
  "is_wide": true,
  "branches": [
    "Жанр музыки (рок, поп, классика)",
    "Музыкальные инструменты",
    "Концерты и фестивали",
    "Музыкальное оборудование"
  ],
  "question": "Какой аспект музыки интересует получателя больше всего?",
  "refined_topic": null
}
```
- classify_topic
```json
{
  "is_wide": true,
  "branches": [
    "Жанр музыки (рок, поп, классика)",
    "Музыкальные инструменты",
    "Концерты и фестивали",
    "Музыкальное оборудование"
  ],
  "question": "Какой аспект музыки интересует получателя больше всего?",
  "refined_topic": null
}
```

**Checks**
- [PASS] is_wide present
- [PASS] wide topic likely
- [PASS] wide topic has question
- [PASS] wide topic has branches

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
- `generate_personalized_probe:dead_end`: 0.81s

**Outputs**
- llm_raw:generate_personalized_probe:dead_end
```json
{
  "question": "Как ваш близкий человек обычно проводит время, слушая свои виниловые пластинки? Есть ли у него особый ритуал или место, где он любит наслаждаться музыкой?",
  "options": [
    "Он часто слушает музыку в одиночестве",
    "Он любит делиться музыкой с друзьями и семьей",
    "У него есть особое место в доме, где он хранит и слушает винил",
    "Он часто слушает музыку, выполняя другие задачи, такие как чтение или работа"
  ]
}
```
- probe
```json
{
  "question": "Как ваш близкий человек обычно проводит время, слушая свои виниловые пластинки? Есть ли у него особый ритуал или место, где он любит наслаждаться музыкой?",
  "options": [
    "Он часто слушает музыку в одиночестве",
    "Он любит делиться музыкой с друзьями и семьей",
    "У него есть особое место в доме, где он хранит и слушает винил",
    "Он часто слушает музыку, выполняя другие задачи, такие как чтение или работа"
  ]
}
```

**Checks**
- [PASS] probe has question

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
- `generate_topic_hints`: 1.74s

**Outputs**
- llm_raw:generate_topic_hints
```json
[
  {
    "question": "Есть ли у него особое место, где он любит пить кофе или расслабляться после долгого дня?",
    "reasoning": "Чтобы исследовать домашнюю среду и потенциальные ритуалы, связанные с кофе"
  },
  {
    "question": "Участвует ли он в каких-либо спортивных или активных занятиях, которые требуют регулярной физической нагрузки?",
    "reasoning": "Чтобы изучить его физическую активность и потенциальные интересы, связанные со здоровьем и фитнесом"
  },
  {
    "question": "Есть ли у него близкий друг или знакомый, который разделяет его интересы и может влиять на его хобби?",
    "reasoning": "Чтобы исследовать его социальный круг и потенциальные интересы, которые могут быть под влиянием друзей"
  },
  {
    "question": "Имеет ли он какую-либо творческую страсть или хобби, которое он не связывает напрямую с работой или кофе?",
    "reasoning": "Чтобы раскрыть потенциальные творческие интересы и хобби, которые могут не быть сразу очевидны"
  },
  {
    "question": "Есть ли у него какие-либо планы на ближайшее будущее, такие как путешествия, обучение или карьерные изменения?",
    "reasoning": "Чтобы изучить его цели и стремления, и потенциально выявить новые интересы или темы"
  }
]
```
- topic_hints
```json
[
  {
    "question": "Есть ли у него особое место, где он любит пить кофе или расслабляться после долгого дня?",
    "reasoning": "Чтобы исследовать домашнюю среду и потенциальные ритуалы, связанные с кофе"
  },
  {
    "question": "Участвует ли он в каких-либо спортивных или активных занятиях, которые требуют регулярной физической нагрузки?",
    "reasoning": "Чтобы изучить его физическую активность и потенциальные интересы, связанные со здоровьем и фитнесом"
  },
  {
    "question": "Есть ли у него близкий друг или знакомый, который разделяет его интересы и может влиять на его хобби?",
    "reasoning": "Чтобы исследовать его социальный круг и потенциальные интересы, которые могут быть под влиянием друзей"
  },
  {
    "question": "Имеет ли он какую-либо творческую страсть или хобби, которое он не связывает напрямую с работой или кофе?",
    "reasoning": "Чтобы раскрыть потенциальные творческие интересы и хобби, которые могут не быть сразу очевидны"
  },
  {
    "question": "Есть ли у него какие-либо планы на ближайшее будущее, такие как путешествия, обучение или карьерные изменения?",
    "reasoning": "Чтобы изучить его цели и стремления, и потенциально выявить новые интересы или темы"
  }
]
```

**Checks**
- [PASS] hints not empty

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

**LLM Timings**
- `normalize_topics`: 0.29s
- `generate_hypotheses_bulk`: 1.42s

**Outputs**
- llm_raw:normalize_topics
```json
[
  "Кофе"
]
```
- llm_raw:generate_hypotheses_bulk
```json
{
  "Кофе": {
    "is_wide": false,
    "hypotheses": [
      {
        "title": "Абонемент на кофе в кофейне",
        "description": "Подарите возможность наслаждаться кофе в кофейне каждый день",
        "primary_gap": "the_permission",
        "reasoning": "Поскольку интересы получателя включают кофе, абонемент на кофе в кофейне даст ему возможность наслаждаться кофе без чувства вины и ограничений",
        "search_queries": [
          "абонемент на кофе в кофейне",
          "кофейный клуб"
        ]
      },
      {
        "title": "Кофеварка для дома",
        "description": "Помогите получателю наслаждаться кофе дома с помощью кофеварки",
        "primary_gap": "the_optimizer",
        "reasoning": "Кофеварка для дома сделает процесс приготовления кофе проще и более удобным для получателя",
        "search_queries": [
          "кофеварка для дома",
          "кофемашина"
        ]
      },
      {
        "title": "Курс по кофе и его приготовлению",
        "description": "Подарите получателю курс по кофе и его приготовлению, чтобы он мог узнать больше о кофе",
        "primary_gap": "the_catalyst",
        "reasoning": "Курс по кофе и его приготовлению позволит получателю узнать больше о кофе и улучшить свои навыки в приготовлении кофе",
        "search_queries": [
          "курс по кофе",
          "кофе и его приготовление"
        ]
      }
    ]
  }
}
```

**Checks**
- [PASS] interaction persisted
- [PASS] hypothesis reaction updated — reaction=like

---
