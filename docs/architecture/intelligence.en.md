# Gifty Intelligence API Contract

Этот документ описывает API, который должен предоставлять внешний сервис интеллекта (`api.giftyai.ru`) для интеграции с основным бэкендом Gifty.

**Базовый URL:** `https://api.giftyai.ru`
**Авторизация:** Bearer Token (в заголовке `Authorization`)

---

## 1. Классификация категорий

Используется для маппинга названий категорий с сайтов-доноров во внутреннюю систему категорий Gifty.

**Метод:** `POST`
**Путь:** `/v1/classify/categories`

**Request Body:**
```json
{
  "external_names": ["Кружки прикольные", "Гаджеты для дома"],
  "internal_categories": [
    {"id": 1, "name": "Кухня"},
    {"id": 2, "name": "Электроника"}
  ]
}
```

**Response Body:**
```json
{
  "mappings": [
    {"external_name": "Кружки прикольные", "internal_category_id": 1},
    {"external_name": "Гаджеты для дома", "internal_category_id": 2}
  ]
}
```

---

## 2. Скорринг товара (Giftability)

Оценка того, насколько товар является хорошим подарком, и генерация пояснения.

**Метод:** `POST`
**Путь:** `/v1/products/score`

**Request Body:**
```json
{
  "title": "Набор для выращивания кристаллов",
  "description": "Развивающий набор для детей...",
  "price": 1500.0,
  "category": "Игрушки"
}
```

**Response Body:**
```json
{
  "gift_score": 9.2,
  "reasoning": "Отличный образовательный подарок для детей младшего школьного возраста. Развивает любознательность.",
  "tags": ["образование", "дети", "наука"]
}
```
