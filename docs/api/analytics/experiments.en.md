# Experiments & A/B Testing 🧪

A system for conducting controlled experiments to optimize AI performance and improve user experience.

### Conducting A/B Tests

To start an experiment, add a configuration to `configs/logic.yaml`. The system will automatically allocate users to groups based on their `session_id`.

**Configuration Example:**
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

### Experiment Analysis (`experimentReport`)

GraphQL query to compare the efficiency of different variants.

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
      conversionRate   # % of likes vs total hypotheses
      avgLatencyMs
      totalCostUsd
    }
  }
}
```

