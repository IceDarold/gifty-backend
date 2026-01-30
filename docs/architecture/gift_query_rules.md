# Gift Query & Feedback Strategy

> **"Мы не спрашиваем абстрактно. Мы калибруем 5 Dimensions."**

Этот документ описывает логику сбора информации о пользователе (Quiz) и динамического уточнения предпочтений (Feedback Loop). Цель — построить профиль на основе [Grand Unified Theory of Gifting](grand_unified_theory.md).

---

## 1. Onboarding Quiz (Static Profiling)

Задача: за 12–16 вопросов построить базовый профиль весов для 5 измерений.

### Module 1: Context (Calibration)
*Калибрует допустимость личных подарков.*

1.  **Relation**: Кто он вам? (Коллега → Anchor low / Партнер → Anchor high)
2.  **Occasion**: Повод и тон? (Формально, Романтично, "Вау-эффект")
3.  **Constraints**: Бюджет, сроки, тип (Вещь vs Впечатление).

### Module 2: The Mirror (Identity)
*Определяет: Fanatic, Aesthetic, Taste Token, Values, Tribe, Personal Myth.*

4.  **Stable Traits**: Теги личности (Эстет, Гик, Спортсмен, Путешественник...).
5.  **Fandoms**: Текущие увлечения (ввод текста). → *Fanatic*.
6.  **Aesthetic Score**: Выбор вайба (Минимал, Уют, Тек, Винтаж). → *Aesthetic*.
7.  **Micro-Preferences**: Придирчивость к деталям (Кофе, Канцелярия, Звук). → *Taste Token*.

### Module 3: The Optimizer (Friction)
*Определяет: Upgrade, Fix, System, Automation, Buffer, Comfort.*

8.  **Pain Points**: Что "болит"? (Время, Порядок, Усталость, Стресс, Быт).
9.  **Solution Style**:
    *   "Улучшить то, что есть" → *Upgrade*.
    *   "Убрать раздражалку" → *Fix*.
    *   "Навести систему" → *System*.
    *   "Пусть само делается" → *Automation*.
10. **Tech Tolerance**: Насколько сложно настроить? (Plug&Play vs Любит возиться).

### Module 4: The Catalyst (Potential)
*Определяет: Starter, Commitment, Accelerator, Horizon, Confindence.*

11. **Aspirations**: "Хочу, но не начал" (Спорт, Язык, Творчество...).
12. **Stage**: Думает → Пробует → Регулярно.
13. **Effort Tolerance**: Любит вызов vs Не любит "домашку".

### Module 5: The Anchor (Connection)
*Определяет: Time Capsule, Inside Language, Rituals*.

14. **Intimacy Score**: Насколько уместен личный подарок (0-10).
15. **Shared History**: Есть ли общий контекст/шутка? (Да/Нет).

### Module 6: The Permission (Guilt)
*Определяет: Quiet Premium, Sensory, Rest, Play, Status.*

16. **Self-Indulgence**: Покупает себе приятное? (Часто/Редко).
17. **Pleasure Type**: Уют, Вкус, Красота, Игра, Статус.

---

## 2. Dynamic Feedback Loop (In-Scroll)

Принцип: **1 Click → 1 Micro-Question**. Мы спрашиваем *почему* реакция такая.

### Event A: Like (👍)
**"Что именно понравилось?"**
*   "Стиль / Эстетика" → `Mirror: Aesthetic` +
*   "Прямо про него" → `Mirror: Personal Myth` +
*   "Полезно / Удобно" → `Optimizer` + (уточнить: Fix/System?)
*   "Милое / Про нас" → `Anchor` +
*   "Сам бы не купил, но кайф" → `Permission` +
*   "Для роста / Хобби" → `Catalyst` +

### Event B: Dislike (👎)
**"Почему не подходит?"**
*   "Не его стиль" → `Mirror: Aesthetic` (сменить вектор).
*   "Бесполезно" → `Permission` - / `Optimizer` ++.
*   "Слишком личное" → `Anchor` limit.
*   "Слишком сложно" → `Catalyst` limit.
*   "Уже есть" → Предложить `Optimizer: Upgrade`.
*   "Выглядит как хлам" → Clutter filter.

### Event C: Doubt (🤔)
**"Что мешает?"**
*   Цена / Доставка / Риск / Банально.

---

## 3. Smart Questioning Logic

Система не задает случайные вопросы. Она бьет в точку с максимальной неопределенностью.

1.  **Dominant Dimension**: Если 3 лайка подряд за "Пользу", система понимает: "Ага, мы в Optimizer".
2.  **Subtype Fork**: Следующий вопрос уточняет подтип внутри победителя.
    *   *System*: "Ему важнее качество (Upgrade) или автоматизация (Automation)?"

---

## 4. Safety Filters (Fast Scales)

Быстрые вопросы, чтобы отсечь 80% неудач:
*   **Minimalism vs Stuff**: Фильтр хлама.
*   **Sentimentality (0-10)**: Фильтр "милых пылесборников".
*   **Risk Tolerance**: Сюрприз vs Вишлист.
*   **Practicality Scale**: Permission vs Optimizer.
