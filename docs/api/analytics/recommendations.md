# AI-Гипотезы и Рекомендации ✨

Анализ качества работы рекомендательного движка.

### Здоровье Системы (`systemHealth`)

Сводный показатель (Health Score), учитывающий охват каталога и реакции пользователей.

**Query:**
```graphql
query {
  systemHealth {
    healthScore
    status
    catalogCoverage {
      score
      hitRate
    }
    recommendationRelevance {
      score
      likeRate
    }
    searchLatency {
      avgMs
    }
  }
}
```

---

### Детали Гипотезы (`hypothesisDetails`)

Углубленный анализ конкретной идеи подарка: какие запросы делал ИИ, сколько товаров нашел и какие именно товары были показаны.

**Query:**
```graphql
query GetHypothesis($id: UUID!) {
  hypothesisDetails(id: $id) {
    id
    title
    reaction
    searchQueries
    totalResultsFound
    products
  }
}
```
