# Recommendation Quality & AI 🧠

Analysis of gift ideas (hypotheses) proposed by the AI and user reactions to them.

### 1. Hypothesis Analytics (`/catalog/hypotheses`)
Basic statistics on user preferences for suggested topics.

*   **URL**: `/analytics/catalog/hypotheses`
*   **Method**: `GET`
*   **Response Fields**: `like_rate`, `dislike_rate`, `top_performing_topics`.

---

### 2. Recommendation Funnel (`/catalog/hypotheses/funnel`)
Detailed funnel tracking from idea generation to product click.

*   **URL**: `/analytics/hypotheses/funnel`
*   **Stages**: Generated → Shown → Covered (by Catalog) → Interested (Like) → Clicks.

---

### 3. Period/Model Comparison (`/catalog/hypotheses/compare`)
A/B testing tool for prompts and LLM versions. Compares `hit_rate` and `like_rate` between two samples.

*   **URL**: `/analytics/hypotheses/compare`

---

### 4. Hypothesis Details (`/catalog/hypotheses/details`)
All metrics for a specific hypothesis: linked queries, products found, clicks.

*   **URL**: `/analytics/hypotheses/details?hypothesis_id=...`

---

### 5. System Health Score (`/catalog/health`)
Global health metric for the AI + Catalog ecosystem. Aggregates coverage, relevance, and latency.

*   **URL**: `/analytics/catalog/health`
*   **Status**: `healthy`, `degraded`, or `critical`.
