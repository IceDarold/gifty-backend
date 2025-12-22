# Gift query rules v1

Цель: описать статический ruleset для генерации конкретных поисковых запросов в Takprodam Publisher API на основе ответов квиза.

## Формат и поля

Файл: `config/gift_query_rules.v1.yaml`

Верхний уровень:

- `version`: версия правил.
- `meta`: описание ruleset.
- `limits`: лимиты генерации.
- `age_segments`: сегменты по возрасту с `age_min`/`age_max`, `base_queries` и `vibes`.
- `relationship_map`: маппинг отношений.
- `occasion_map`: маппинг поводов.
- `interests_map`: маппинг интересов.
- `gender_map`: маппинг пола получателя (male/female/unisex).
- `description_keywords_map`: словарь подстрок/стемов из свободного описания -> queries.
- `banned`: запреты и негативные ключевые слова.

## Сегментация по возрасту

Выбор сегмента однозначный: берется первый `age_segments.*`, где `age_min <= recipient_age <= age_max`.

## Объединение buckets

Формируйте кандидаты запросов из следующих buckets:

1. `age_segments.<segment>.base_queries`
2. `age_segments.<segment>.vibes.<vibe>.queries` (если vibe указан)
3. `interests_map.<interest>.queries` для каждого interest
4. `gender_map.<gender>.queries` (если gender указан)
5. `description_keywords_map` по подстрокам из `interests_description`
6. `relationship_map.<relationship>.queries`
7. `occasion_map.<occasion>.queries`

Далее объединяйте, убирайте дубли, фильтруйте banned, затем применяйте лимиты.

## Лимиты

- `max_queries_per_bucket`: сколько максимум взять из каждого bucket.
- `max_queries_total`: верхний предел итогового списка.
- `min_queries_total`: нижний предел, при нехватке допускается брать больше из base или interest buckets.
- `max_keywords_from_description`: максимум ключевых слов из `interests_description`.

## Banned и negative_keywords

- `banned.banned_queries` исключаются до формирования итогового списка.
- `banned.negative_keywords` используются для пост-фильтрации результатов Takprodam (товары с такими подстроками исключаются).

## Примеры

### Ребенок 8 лет, vibe: fun

- segment: `child`
- buckets: child.base + child.vibes.fun + relationship + occasion + interests
- пример итоговых запросов: `настольная игра`, `конструктор`, `радиоуправляемая машинка`, `набор фокусов`, `слайм набор`

### Взрослый 32 года, vibe: cozy

- segment: `adult`
- buckets: adult.base + adult.vibes.cozy + relationship + occasion + interests
- пример итоговых запросов: `плед`, `аромасвеча`, `диффузор`, `подушка`, `ночник`

### Mature 60 лет, vibe: practical, interest: health

- segment: `mature`
- buckets: mature.base + mature.vibes.practical + interests.health
- пример итоговых запросов: `массажер`, `тонометр`, `ортопедическая подушка`, `термос`, `чайник`
