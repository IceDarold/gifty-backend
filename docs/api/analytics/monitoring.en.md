# Technical Monitoring 🛠️

Health metrics for the API and data collection systems.

### 1. Technical Health (`/technical`)
Aggregates system health metrics from Prometheus and Loki.

*   **URL**: `/analytics/technical`
*   **Method**: `GET`
*   **Response**:
    ```json
    {
      "api_health": "healthy",
      "requests_per_minute": 120.5,
      "error_rate_5xx": 0.001,
      "active_workers": 4,
      "last_errors": ["Error in search vector...", "Timeout connecting to LLM..."],
      "last_updated": "2024-02-10T12:00:00Z"
    }
    ```

---

### 2. Scraping Monitoring (`/scraping`)
Provides detailed information about the data parsing subsystem.

*   **URL**: `/analytics/scraping`
*   **Method**: `GET`
*   **Response**:
    ```json
    {
      "active_sources": 12,
      "unmapped_categories": 5,
      "total_scraped_items": 45000,
      "ingestion_errors": 2,
      "spiders": {
        "ozon": { "items_scraped": 15000 },
        "wildberries": { "items_scraped": 30000 }
      }
    }
    ```
