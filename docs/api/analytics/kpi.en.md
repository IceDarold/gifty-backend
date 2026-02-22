# Business Metrics and KPI 📊

All primary metrics are now available via a single GraphQL query.

### Core KPI (`stats`)

Returns DAU, quiz completion rate, and gift CTR.

**Query:**
```graphql
query {
  stats {
    dau
    quizCompletionRate
    giftCtr
    totalSessions
    lastUpdated
  }
}
```

---

### Trends and Charts (`trends`)

Returns time series for building linear charts.

**Query:**
```graphql
query GetTrends($days: Int!) {
  trends(days: $days) {
    dates
    dauTrend
    quizStarts
    lastUpdated
  }
}
```

---

### Conversion Funnel (`funnel`)

User progression through major product stages over the last 30 days.

**Query:**
```graphql
query {
  funnel {
    name
    count
    conversionRate
  }
}
```
