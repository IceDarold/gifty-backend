# Experiments & A/B Testing (API) 🧪

Техническое описание эндпоинтов для анализа результатов A/B тестирования.

### Проведение A/B Тестов

Для запуска эксперимента необходимо добавить конфигурацию в `configs/logic.yaml`.

**Пример конфигурации:**
```yaml
experiments:
  - id: "model_comparison_v1"
    is_active: true
    variants:
      variant_a:
        name: "Claude (Control)"
        overrides:
          llm_model_smart: "claude-3-5-sonnet-20260217"
      variant_b:
        name: "GPT-4o (Experiment)"
        overrides:
          llm_model_smart: "gpt-4o"
```

---

### GraphQL API: Анализ результатов (`experimentReport`)

GraphQL запрос для сравнения эффективности различных вариантов.

**Query:**
```graphql
query {
  experimentReport(experimentId: "model_comparison_v1") {
    experimentId
    totalRequests
    variants {
      variantId
      variantName
      requestsCount
      conversionRate   # % лайков к общему числу гипотез
      avgLatencyMs
      totalCostUsd
    }
  }
}
```

---

📖 **Подробное описание философии и архитектуры экспериментов доступно в [Analytics & Monitoring -> Experiments](../../analytics_monitoring/experiments.md).**
