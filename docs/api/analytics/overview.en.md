# Analytics API Overview 📈

This section provides a detailed description of the Gifty internal analytics endpoints. The API acts as a secure proxy between the internal dashboard and data collection systems (PostHog, Prometheus, PostgreSQL).

## Authentication

All requests to the Analytics API require an access token in the `X-Analytics-Token` header.

| Header | Description |
| :--- | :--- |
| `X-Analytics-Token` | Secret token defined in settings (`ANALYTICS_API_TOKEN`). |

---

## Caching
To reduce load on external services, Redis is used:

- Behavioral data (PostHog): 5-10 minutes.
- Technical metrics (Prometheus): 1 minute.
- Errors (Loki): 1 minute.
