# Catalog Coverage Analysis 📦

Tools to evaluate how well the product inventory matches user and AI requests.

### 1. Current Coverage (`/catalog/coverage`)
General search effectiveness snapshot.

*   **URL**: `/analytics/catalog/coverage`
*   **Method**: `GET`
*   **Parameters**:
    - `days` (query, optional): depth of analysis in days (default: 7).
*   **Response Fields**:
    - `hit_rate`: % of queries with at least one result.
    - `avg_results_per_search`: Average number of products found.
    - `top_catalog_gaps`: Most frequent queries with 0 results.

---

### 2. Coverage Trends (`/catalog/coverage/trends`)
Time-series data for catalog completeness. Tracks the impact of content updates.

*   **URL**: `/analytics/catalog/coverage/trends`
*   **Method**: `GET`

---

### 3. Coverage Segments (`/catalog/coverage/segments`)
Segment-based analysis by budget, model, or track.

*   **URL**: `/analytics/catalog/coverage/segments`
*   **Parameters**:
    - `group_by`: `budget`, `model`, or `track`.

---

### 4. Query Drill-down (`/catalog/coverage/drilldown`)
Deep-dive into specific search patterns to identify reasons for product absences.

*   **URL**: `/analytics/catalog/coverage/drilldown?query=...`
*   **Purpose**: Understand context (models, sessions) where search failures occurred.
