# LLM Quality Report — 2026-02-17 14:36:22

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
- `normalize_topics`: 0.51s
- `generate_hypotheses_bulk`: 2.24s
- `classify_topic`: 0.59s
- `classify_topic`: 0.59s
- `classify_topic`: 0.60s
- `generate_hypotheses`: 1.95s
- `generate_hypotheses`: 2.27s
- `generate_hypotheses`: 2.28s

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
        "description": "Лего набор, который позволит ему выражать свою креативность и расслабляться",
        "primary_gap": "the_mirror",
        "reasoning": "Поскольку он интересуется Лего, этот набор поможет ему проявить свою индивидуальность и получить удовольствие от творческого процесса",
        "search_queries": [
          "Лего наборы для взрослых",
          "Лего креативные наборы"
        ]
      },
      {
        "title": "Лего календарь",
        "description": "Лего календарь, который будет помогать ему планировать и организовывать свою жизнь",
        "primary_gap": "the_optimizer",
        "reasoning": "Этот календарь позволит ему использовать Лего для повышения своей продуктивности и организации",
        "search_queries": [
          "Лего календарь",
          "Лего планировщик"
        ]
      },
      {
        "title": "Лего книга",
        "description": "Книга о истории и развитии Лего, которая поможет ему узнать больше о его хобби",
        "primary_gap": "the_catalyst",
        "reasoning": "Эта книга позволит ему расширить свои знания и интересы в области Лего",
        "search_queries": [
          "Лего книга",
          "История Лего"
        ]
      }
    ]
  },
  "Кофе": {
    "is_wide": false,
    "hypotheses": [
      {
        "title": "Кофемашинка",
        "description": "Кофемашинка, которая позволит ему готовить кофе дома",
        "primary_gap": "the_optimizer",
        "reasoning": "Эта кофемашинка сделает его жизнь проще и комфортнее, позволяя ему наслаждаться кофе дома",
        "search_queries": [
          "Кофемашинка",
          "Домашняя кофемашинка"
        ]
      },
      {
        "title": "Кофейный набор",
        "description": "Набор кофе с不同ными вкусами и ароматами",
        "primary_gap": "the_mirror",
        "reasoning": "Этот набор позволит ему попробовать новые виды кофе и найти свой любимый",
        "search_queries": [
          "Кофейный набор",
          "Кофе набор"
        ]
      },
      {
        "title": "Кофе курс",
        "description": "Курс по приготовлению кофе, который поможет ему улучшить свои навыки",
        "primary_gap": "the_catalyst",
        "reasoning": "Этот курс позволит ему узнать больше о кофе и улучшить свои навыки в приготовлении кофе",
        "search_queries": [
          "Кофе курс",
          "Курс по приготовлению кофе"
        ]
      }
    ]
  },
  "Путешествия": {
    "is_wide": true,
    "question": "В какой тип путешествий он больше всего интересуется? Например, пляжный отдых, городские туры или приключенческие путешествия?",
    "branches": [
      "Пляжный отдых",
      "Городские туры",
      "Приключенческие путешествия"
    ]
  }
}
```
- llm_raw:classify_topic
```json
{
  "is_wide": false,
  "branches": null,
  "question": null,
  "refined_topic": "Лего для взрослых"
}
```
- llm_raw:classify_topic
```json
{
  "is_wide": false,
  "branches": null,
  "question": null,
  "refined_topic": "Путешествия с кофе"
}
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
- llm_raw:generate_hypotheses
```json
[
  {
    "title": "Лего-путешествие по миру",
    "description": "Набор Лего, посвященный знаковым достопримечательностям мира, который сочетает любовь к путешествиям и Лего",
    "primary_gap": "the_catalyst",
    "reasoning": "Поскольку интересы получателя включают путешествия, этот набор может стать катализатором для изучения новых мест и культур, даже если физически он не может путешествовать",
    "search_queries": [
      "Лего достопримечательности",
      "Лего путешествия",
      "Лего мира"
    ]
  },
  {
    "title": "Лего-кафемания",
    "description": "Набор Лего, посвященный кофе, который может украсить рабочее место или кухню, сочетая любовь к кофе и Лего",
    "primary_gap": "the_mirror",
    "reasoning": "Поскольку получатель интересуется кофе и Лего, этот набор может стать отражением его интересов и вкуса",
    "search_queries": [
      "Лего кофе",
      "Лего кофейня",
      "Лего кухня"
    ]
  },
  {
    "title": "Лего-терапия",
    "description": "Набор Лего, предназначенный для расслабления и снятия стресса, который может помочь в повседневной жизни",
    "primary_gap": "the_optimizer",
    "reasoning": "Поскольку получатель, возможно, испытывает стресс в повседневной жизни, этот набор может стать инструментом для оптимизации его психического состояния",
    "search_queries": [
      "Лего терапия",
      "Лего расслабление",
      "Лего стресс"
    ]
  },
  {
    "title": "Лего-вызов",
    "description": "Сложный набор Лего, который может стать вызовом для получателя и помочь ему развить новые навыки",
    "primary_gap": "the_catalyst",
    "reasoning": "Поскольку получатель, возможно, ищет новые вызовы, этот набор может стать катализатором для развития новых навыков и интересов",
    "search_queries": [
      "Сложный Лего",
      "Лего вызов",
      "Лего эксперт"
    ]
  }
]
```
- llm_raw:generate_hypotheses
```json
[
  {
    "title": "Лего-кофейный журнал",
    "description": "Уникальный журнал, сочетающий любовь к кофе и Лего, для ведения заметок и планирования",
    "primary_gap": "the_catalyst",
    "reasoning": "Поскольку интересы получателя включают Лего и кофе, этот журнал может поддержать его творческий рост и организацию. Это также может быть связано с его интересом к путешествиям, где ведение журнала может быть полезным",
    "search_queries": [
      "Лего кофейный журнал",
      "Креативный кофейный журнал",
      "Лего организатор"
    ]
  },
  {
    "title": "Персонализированная Лего-кофейная чашка",
    "description": "Чашка, на которой изображена персонализированная Лего-фигурка или дизайн, созданный получателем",
    "primary_gap": "the_mirror",
    "reasoning": "Эта чашка будет отражать личность и интересы получателя, делая его ежедневный ритуал кофепитья более персонализированным и приятным. Это также может быть связано с его интересом к Лего и кофе",
    "search_queries": [
      "Персонализированная Лего чашка",
      "Лего кофейная чашка",
      "Кастомная Лего кружка"
    ]
  },
  {
    "title": "Кофейный набор для путешествий с Лего-темой",
    "description": "Набор для приготовления кофе в пути, включающий Лего-тематический контейнер или аксессуары",
    "primary_gap": "the_optimizer",
    "reasoning": "Поскольку получатель интересуется путешествиями, этот набор может сделать его кофейный ритуал более удобным и приятным в пути. Лего-тема добавит ему личный штрих",
    "search_queries": [
      "Кофейный набор для путешествий",
      "Лего кофейный контейнер",
      "Портативный кофейный набор"
    ]
  },
  {
    "title": "Лего-кофейный опыт",
    "description": "Опыт, сочетающий кофе и Лего, такой как кофейная дегустация или Лего-мастерская",
    "primary_gap": "the_anchor",
    "reasoning": "Этот опыт может укрепить связь между получателем и другими людьми, которые разделяют его интересы. Это также может быть уникальным и запоминающимся опытом, который он сможет поделиться с другими",
    "search_queries": [
      "Лего кофейный опыт",
      "Кофейная дегустация",
      "Лего мастерская"
    ]
  }
]
```
- llm_raw:generate_hypotheses
```json
[
  {
    "title": "Кофейный Путеводитель",
    "description": "Путеводитель по кофейным магазинам и кафе в разных городах и странах",
    "primary_gap": "the_catalyst",
    "reasoning": "Поскольку интересы получателя включают путешествия и кофе, этот подарок поддержит его рост и развитие как кофейного ценителя, предоставляя новые знания и впечатления.",
    "search_queries": [
      "кофейный путеводитель",
      "кофе путешествия",
      "кофейные магазины мира"
    ]
  },
  {
    "title": "Портативная Кофемашинка для Путешествий",
    "description": "Легкая и компактная кофемашинка, идеальная для путешествий и походов",
    "primary_gap": "the_optimizer",
    "reasoning": "Этот подарок сделает жизнь получателя более комфортной и приятной во время путешествий, позволяя ему наслаждаться любимым кофе в любом месте.",
    "search_queries": [
      "портативная кофемашинка",
      "кофе для путешествий",
      "компактная кофемашина"
    ]
  },
  {
    "title": "Кофейный Абонемент с Путешествиями",
    "description": "Абонемент на регулярную доставку кофе из разных стран и регионов, с информацией о происхождении и культуре",
    "primary_gap": "the_permission",
    "reasoning": "Этот подарок даст получателю возможность наслаждаться разнообразными кофе и узнать о новых культурах, предоставляя ему разрешение наслаждаться новыми впечатлениями и расширять свои горизонты.",
    "search_queries": [
      "кофейный абонемент",
      "кофе подписка",
      "кофе из разных стран"
    ]
  },
  {
    "title": "Персонализированный Кофейный Журнал для Путешествий",
    "description": "Журнал для записи впечатлений и заметок о кофе, пробуемом во время путешествий, с персонализированной обложкой",
    "primary_gap": "the_mirror",
    "reasoning": "Этот подарок позволит получателю отразить свою личность и интересы, а также сохранить воспоминания о кофе и путешествиях, что соответствует его ценностям и увлечениям.",
    "search_queries": [
      "персонализированный кофейный журнал",
      "кофе журнал",
      "путешествия журнал"
    ]
  }
]
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
      "Лего-путешествие по миру",
      "Лего-кафемания",
      "Лего-терапия",
      "Лего-вызов"
    ],
    "question": null,
    "question_options": []
  },
  {
    "topic": "Кофе",
    "status": "ready",
    "hypotheses": [
      "Лего-кофейный журнал",
      "Персонализированная Лего-кофейная чашка",
      "Кофейный набор для путешествий с Лего-темой",
      "Лего-кофейный опыт"
    ],
    "question": null,
    "question_options": []
  },
  {
    "topic": "Путешествия",
    "status": "ready",
    "hypotheses": [
      "Кофейный Путеводитель",
      "Портативная Кофемашинка для Путешествий",
      "Кофейный Абонемент с Путешествиями",
      "Персонализированный Кофейный Журнал для Путешествий"
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
- `normalize_topics`: 0.32s
- `generate_hypotheses_bulk`: 1.82s

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
    "question": "Какая область музыки больше всего интересует получателя?",
    "branches": [
      "Виниловые пластинки",
      "Билеты на концерты",
      "Оборудование для домашней студии"
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
    "question": "Какая область музыки больше всего интересует получателя?",
    "question_options": [
      "Виниловые пластинки",
      "Билеты на концерты",
      "Оборудование для домашней студии"
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
- `normalize_topics`: 0.37s

**Outputs**
- llm_raw:normalize_topics
```json
[
  "Виниловые проигрыватели"
]
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

**LLM Timings**
- `normalize_topics`: 0.48s

**Outputs**
- llm_raw:normalize_topics
```json
[
  "Кофе"
]
```

---
