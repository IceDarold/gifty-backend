# Analytics API

PostHog-powered analytics proxy for Gifty internal dashboard.

## Overview

This module provides three REST endpoints that serve aggregated analytics data from PostHog to the internal analytics dashboard (`analytics.giftyai.ru`). All data is cached in Redis for 5-15 minutes to reduce load on PostHog API.

## Architecture

```
Frontend (analytics.giftyai.ru)
    ↓ HTTP GET
Backend (/analytics/*)
    ↓ Check Redis cache
    ↓ (if miss) Query PostHog API
PostHog Cloud (app.posthog.com)
```

## Endpoints

| Endpoint | Purpose | Cache TTL |
|----------|---------|-----------|
| `GET /analytics/stats` | KPI cards (DAU, completion rate, CTR) | 5 min |
| `GET /analytics/trends?days=7` | Time-series data for charts | 10 min |
| `GET /analytics/funnel` | Conversion funnel visualization | 10 min |

## Configuration

Required environment variables:

```bash
POSTHOG_API_KEY=phx_...        # Personal API Key (not Project Key!)
POSTHOG_PROJECT_ID=303298      # Your PostHog project ID
REDIS_URL=redis://redis:6379   # For caching
```

## PostHog Events

The analytics rely on these events being tracked on the frontend:

- `page_viewed` - Page navigation (for DAU calculation)
- `quiz_started` - User began quiz
- `quiz_completed` - User finished quiz
- `results_shown` - Gift recommendations displayed
- `gift_clicked` - User clicked on a gift (critical for CTR!)

## Implementation Details

### Query API

We use PostHog's **Query API** (`/api/projects/{id}/query/`) with structured queries:

**TrendsQuery** (for DAU, quiz starts):
```python
{
    "kind": "TrendsQuery",
    "series": [{"event": "page_viewed", "math": "dau"}],
    "dateRange": {"date_from": "-7d"},
    "interval": "day"
}
```

**FunnelsQuery** (for conversion rates):
```python
{
    "kind": "FunnelsQuery",
    "series": [
        {"event": "quiz_started"},
        {"event": "quiz_completed"}
    ],
    "dateRange": {"date_from": "-7d"}
}
```

### Error Handling

All endpoints return **graceful fallback** with zero values if PostHog is unavailable:

```json
{
  "dau": 0,
  "quiz_completion_rate": 0.0,
  "error": "PostHog API error: ..."
}
```

This ensures the frontend never breaks, even if analytics data is temporarily unavailable.

## Testing

### Local Testing

```bash
# Start services
docker compose up

# Test endpoints
curl http://localhost:8000/analytics/stats
curl http://localhost:8000/analytics/trends?days=30
curl http://localhost:8000/analytics/funnel
```

### Production Testing

```bash
curl https://api.giftyai.ru/analytics/stats
```

## Monitoring

- **Logs**: Check `docker compose logs api` for PostHog API errors
- **Redis**: Monitor cache hit rate with `redis-cli INFO stats`
- **PostHog**: Check API usage at app.posthog.com/settings/project

## Performance

- **Response time**: ~50-200ms (cached) / ~1-3s (cache miss)
- **Cache hit rate**: ~95% (with 5-min TTL)
- **PostHog API calls**: ~10-20 per hour (with caching)

## Future Improvements

- [ ] Add real-time updates via WebSocket
- [ ] Implement custom date range filters
- [ ] Add segmentation (by traffic source, device)
- [ ] Export data to CSV/Excel
- [ ] A/B test comparison views
- [ ] Retention cohort analysis

## Documentation

- **Frontend Integration**: `/docs/guides/analytics_frontend_integration.md`
- **Quick Start**: `/docs/guides/analytics_api_quickstart.md`
- **PostHog Docs**: https://posthog.com/docs/api/query

## Support

- **Slack**: `#gifty-backend`
- **Issues**: GitHub Issues
- **PostHog Support**: support@posthog.com
