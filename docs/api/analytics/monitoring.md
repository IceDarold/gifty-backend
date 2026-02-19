# Технический Мониторинг 🛠️

Метрики здоровья API и систем сбора данных.

### 1. Техническое состояние (`/technical`)
Агрегирует метрики здоровья системы из Prometheus и Loki.

*   **URL**: `/analytics/technical`
*   **Метод**: `GET`
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

### 2. Мониторинг Парсинга (`/scraping`)
Предоставляет детальную информацию о работе подсистемы сбора данных.

*   **URL**: `/analytics/scraping`
*   **Метод**: `GET`
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
