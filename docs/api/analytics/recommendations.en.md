# AI Hypotheses and Recommendations ✨

Analysis of recommendation engine performance.

### System Health (`systemHealth`)

Composite score (Health Score) reflecting catalog coverage and user reactions.

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

### Hypothesis Details (`hypothesisDetails`)

Granular analysis of a specific gift idea: search queries used by AI, results found, and products shown.

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
