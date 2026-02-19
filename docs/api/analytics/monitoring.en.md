# Monitoring and Health 🛠️

Technical metrics and spider status.

### Technical Health (`technical`)

Metrics from Prometheus and error logs from Loki.

**Query:**
```graphql
query {
  technical {
    apiHealth
    requestsPerMinute
    errorRate5xx
    lastErrors
    lastUpdated
  }
}
```

---

### Scraper Status (`scraping`)

Monitoring the data collection process.

**Query:**
```graphql
query {
  scraping {
    activeSources
    unmappedCategories
    totalScrapedItems
    ingestionErrors
    spiders
  }
}
```

**Description:**
- `unmappedCategories`: Number of external site categories not yet mapped to Gifty's internal structure.
- `spiders`: Detailed statistics for each active Scrapy spider.
