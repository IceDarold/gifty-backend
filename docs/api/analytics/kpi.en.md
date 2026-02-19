# Business Metrics & KPI 📊

Core product indicators, user funnels, and time-series trends.

### 1. KPI Stats (`/stats`)
Returns key performance indicators for the last 24 hours and 7 days.

*   **URL**: `/analytics/stats`
*   **Method**: `GET`
*   **Response**:
    ```json
    {
      "dau": 150,
      "quiz_completion_rate": 65.5,
      "gift_ctr": 12.3,
      "total_sessions": 450,
      "last_updated": "2024-02-10T12:00:00Z"
    }
    ```

**Response Fields:**
- `dau`: Daily Active Users count for the last 24 hours.
- `quiz_completion_rate`: % of completed quizzes over the last 7 days.
- `gift_ctr`: % of clicks on items relative to total recommendation views.
- `total_sessions`: Total number of started quizzes over the last 7 days.

---

### 2. Trends & Charts (`/trends`)
Returns time-series data for chart visualization.

*   **URL**: `/analytics/trends`
*   **Method**: `GET`
*   **Parameters**:
    - `days` (query, optional): Number of days to analyze (default: 7, max: 90).
*   **Response**:
    ```json
    {
      "dates": ["2024-02-03", "2024-02-04", ...],
      "dau_trend": [120, 145, ...],
      "quiz_starts": [50, 62, ...],
      "last_updated": "2024-02-10T12:00:00Z"
    }
    ```

---

### 3. Conversion Funnel (`/funnel`)
Returns data on users' progress through core product steps over the last 30 days.

*   **URL**: `/analytics/funnel`
*   **Method**: `GET`
*   **Response**:
    ```json
    {
      "steps": [
        { "name": "quiz_started", "count": 1000, "conversion_rate": 100.0 },
        { "name": "quiz_completed", "count": 650, "conversion_rate": 65.0 },
        { "name": "results_shown", "count": 600, "conversion_rate": 92.3 },
        { "name": "gift_clicked", "count": 80, "conversion_rate": 13.3 }
      ],
      "last_updated": "2024-02-10T12:00:00Z"
    }
    ```
