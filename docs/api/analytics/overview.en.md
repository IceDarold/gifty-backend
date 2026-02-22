# Analytics API Overview 📈

The entire Gifty analytics section has been migrated to **GraphQL**. This allows the frontend to request exactly the data needed for a specific dashboard, minimizing server load.

The API acts as a secure proxy between the internal dashboard and data collection systems (PostHog, Prometheus, PostgreSQL).

## Authentication

All requests to the Analytics GraphQL API require an access token in the `X-Analytics-Token` header.

| Header | Description |
| :--- | :--- |
| `X-Analytics-Token` | Secret token set in settings (`ANALYTICS_API_TOKEN`). |

## Endpoint

All requests are directed to a single endpoint:
- **URL**: `/api/v1/analytics/graphql`
- **Method**: `POST` (or `GET` for GraphiQL browser access)

---

## Caching
Redis is used to reduce the load on external services:

- Behavioral data (PostHog): 5-10 minutes.
- Technical metrics (Prometheus): 1 minute.
- System Health (PostgreSQL): 5 minutes.
