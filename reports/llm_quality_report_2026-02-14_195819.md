# LLM Quality Report — 2026-02-14 19:58:19

## Summary
- Total scenarios: 7
- Pass: 6
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
- `normalize_topics`: 0.99s
- `generate_hypotheses_bulk`: 26.06s

**Outputs**
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
    "status": "question",
    "hypotheses": [],
    "question": "Какое направление Лего ему ближе всего? Он собирает сложные коллекционные наборы для взрослых, любит архитектурные модели или, может, предпочитает тематические серии (Star Wars, Technic, Creator)?"
  },
  {
    "topic": "Кофе",
    "status": "ready",
    "hypotheses": [
      "Набор для альтернативного заваривания кофе",
      "Подписка на свежеобжаренный specialty-кофе",
      "Термокружка-тамблер премиум-класса для кофе в дороге"
    ],
    "question": null
  },
  {
    "topic": "Путешествия",
    "status": "question",
    "hypotheses": [],
    "question": "Какой стиль путешествий ему ближе? Это поможет подобрать по-настоящему точный подарок."
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
- `normalize_topics`: 1.20s
- `generate_hypotheses_bulk`: 6.03s

**Outputs**
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
    "question": "Музыка — это целый мир! Подскажите, что ближе всего получательнице: она сама играет на каком-то инструменте, любит ходить на концерты, коллекционирует винил, или просто обожает слушать музыку дома/в наушниках? Может, у неё есть любимый жанр или исполнитель?"
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
- `normalize_topics`: 0.80s
- `generate_hypotheses_bulk`: 27.92s

**Outputs**
- session.topics
```json
[
  "Виниловые проигрыватели",
  "Музыка 70-х годов"
]
```
- tracks.summary
```json
[
  {
    "topic": "Виниловые проигрыватели",
    "status": "ready",
    "hypotheses": [
      "Стилус премиум-класса для винтажного проигрывателя",
      "Набор для профессиональной чистки виниловых пластинок",
      "Винтажный постер/принт культового Hi-Fi оборудования 70-х"
    ],
    "question": null
  },
  {
    "topic": "Музыка 70-х годов",
    "status": "question",
    "hypotheses": [],
    "question": "Музыка 70-х — это очень богатая эпоха! Подскажите, какое направление ему ближе всего? Это поможет найти действительно точный подарок."
  }
]
```

**Checks**
- [PASS] session has tracks or probe
- [PASS] hypotheses have titles
- [PASS] no duplicate hypothesis titles
- [PASS] RU language output

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
- `normalize_topics`: 1.05s
- `generate_hypotheses_bulk`: 46.29s

**Outputs**
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
      "Персональный трекер HRV (вариабельности сердечного ритма)",
      "Красивый набор адаптогенов премиум-класса",
      "Книга «Lifespan» Дэвида Синклера или курс по longevity"
    ],
    "question": null
  },
  {
    "topic": "миксология",
    "status": "ready",
    "hypotheses": [
      "Набор японских барных инструментов (джиггер, барная ложка, стрейнер)",
      "Набор необычных биттеров и тинктур для коктейлей",
      "Силиконовые формы для кристально прозрачного льда"
    ],
    "question": null
  },
  {
    "topic": "инди-игры",
    "status": "question",
    "hypotheses": [],
    "question": "Инди-игры — это целый мир! Подскажите, какой стиль ей ближе? Это поможет найти по-настоящему точный подарок."
  }
]
```

**Checks**
- [PASS] session has tracks or probe
- [PASS] hypotheses have titles
- [PASS] no duplicate hypothesis titles
- [PASS] RU language output

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
- `classify_topic`: 3.10s

**Outputs**
- classify_topic
```json
{
  "is_wide": true,
  "branches": [
    "Инструменты и оборудование (гитара, синтезатор, микрофон и т.д.)",
    "Аудиотехника и звук (наушники, колонки, виниловый проигрыватель)",
    "Обучение и развитие (уроки, курсы, книги по музыке)",
    "Музыкальные аксессуары и мерч (подставки для инструментов, кабели, одежда артистов)"
  ],
  "question": "Спасибо за интерес к музыке! Чтобы найти идеальный подарок, подскажите пожалуйста: музыка — это их хобби (они сами играют/создают музыку) или они больше слушают и наслаждаются музыкой? И если можно, есть ли любимые жанры или стиль музыки?",
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
- `generate_personalized_probe:dead_end`: 5.39s

**Outputs**
- probe
```json
{
  "question": "Когда ваш друг включает винил, что его больше всего привлекает: сам звук и качество музыки, или это момент, когда он замедляется и отключается от всего остального?",
  "options": [
    "Звук и техническое качество — он обсуждает характеристики пластинок и оборудования",
    "Ритуал и атмосфера — включение винила для него это способ создать уютное пространство",
    "Коллекционирование — его привлекает охота за редкими альбомами и сам процесс собирания",
    "Ностальгия и воспоминания — винил связан для него с конкретными периодами жизни или людьми",
    "Социальный аспект — он делится музыкой с друзьями, приглашает людей послушать",
    "Не совсем уверен, что именно его движет"
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
- `generate_topic_hints`: 6.21s

**Outputs**
- topic_hints
```json
[
  {
    "question": "Когда он/она говорит о кофе, это больше про вкус напитка или про ритуал подготовки? Заваривает ли дома или предпочитает кофейни?",
    "reasoning": "Различие между кофе как продуктом vs. кофе как опытом раскроет, есть ли пробел в 'the_anchor' (ритуалы) или 'the_optimizer' (процесс приготовления)"
  },
  {
    "question": "В его/её рабочем пространстве — дома или в офисе — есть ли признаки 'заботы о деталях'? Например, красивая чашка, растение, фото?",
    "reasoning": "Поиск информации об окружающей среде выявит пробел в 'the_mirror' (эстетика/идентичность) или потребность в создании комфортного пространства"
  },
  {
    "question": "Когда в последний раз он/она пробовал(а) что-то новое в области еды или напитков? Или это вообще не в приоритетах?",
    "reasoning": "Это указывает на наличие пробела в 'the_permission' (разрешение себе роскошь) или 'the_catalyst' (поддержка исследования и экспериментов)"
  },
  {
    "question": "Есть ли люди в его/её жизни, с которыми он/она проводит время утром или днём? Есть ли общие 'кофейные' встречи или это одиночное удовольствие?",
    "reasoning": "Определяет потенциальный пробел в 'the_anchor' (общие ритуалы и воспоминания) или 'the_permission' (разрешение себе личное время)"
  },
  {
    "question": "Замечал ли ты, что он/она когда-нибудь жалуется на энергию, сон или концентрацию? Или кажется, что кофе — это часть 'решения' какой-то проблемы?",
    "reasoning": "Выявляет скрытый пробел в 'the_optimizer' (улучшение качества жизни, решение проблем с благополучием)"
  }
]
```

**Checks**
- [PASS] hints not empty

---
