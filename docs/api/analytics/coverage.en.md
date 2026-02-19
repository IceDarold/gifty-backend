# Catalog Coverage 📦

Analysis of how well catalog products match AI-generated search queries.

### Coverage Overview (`catalogCoverage`)

Provides data on Hit Rate (percentage of successful searches) and identifies catalog "gaps."

**Query:**
```graphql
query GetCoverage($days: Int!) {
  catalogCoverage(days: $days) {
    totalSearches
    hitRate
    avgResultsPerSearch
    topCatalogGaps {
      query
      misses
    }
  }
}
```

**Fields Description:**
- `hitRate`: Percentage of searches that returned at least one result.
- `topCatalogGaps`: List of queries that most frequently returned 0 results (a signal to add new scraping sources).
