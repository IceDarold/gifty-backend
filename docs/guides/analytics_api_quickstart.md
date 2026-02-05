# Analytics API Quick Reference

## Endpoints

### 1. KPI Stats
```
GET /analytics/stats
```
```json
{
  "dau": 127,
  "quiz_completion_rate": 68.5,
  "gift_ctr": 42.3,
  "total_sessions": 1543
}
```

### 2. Trends
```
GET /analytics/trends?days=7
```
```json
{
  "dates": ["26-Jan-2026", "27-Jan-2026", ...],
  "dau_trend": [45, 52, 48, ...],
  "quiz_starts": [23, 31, 28, ...]
}
```

### 3. Funnel
```
GET /analytics/funnel
```
```json
{
  "steps": [
    {"name": "quiz_started", "count": 1543, "conversion_rate": 100.0},
    {"name": "quiz_completed", "count": 1057, "conversion_rate": 68.5},
    {"name": "results_shown", "count": 1042, "conversion_rate": 67.5},
    {"name": "gift_clicked", "count": 441, "conversion_rate": 28.6}
  ]
}
```

## Quick Start (React + TypeScript)

```typescript
// types.ts
export interface AnalyticsStats {
  dau: number;
  quiz_completion_rate: number;
  gift_ctr: number;
  total_sessions: number;
  last_updated: string;
  error?: string;
}

export interface TrendsData {
  dates: string[];
  dau_trend: number[];
  quiz_starts: number[];
  last_updated: string;
  error?: string;
}

export interface FunnelStep {
  name: string;
  count: number;
  conversion_rate: number;
}

export interface FunnelData {
  steps: FunnelStep[];
  last_updated: string;
  error?: string;
}

// api.ts
const API_BASE = 'https://api.giftyai.ru';

export const analyticsApi = {
  getStats: () => 
    fetch(`${API_BASE}/analytics/stats`).then(r => r.json()),
  
  getTrends: (days: number = 7) => 
    fetch(`${API_BASE}/analytics/trends?days=${days}`).then(r => r.json()),
  
  getFunnel: () => 
    fetch(`${API_BASE}/analytics/funnel`).then(r => r.json()),
};

// Dashboard.tsx
import { useEffect, useState } from 'react';
import { analyticsApi } from './api';
import type { AnalyticsStats, TrendsData, FunnelData } from './types';

export const AnalyticsDashboard = () => {
  const [stats, setStats] = useState<AnalyticsStats | null>(null);
  const [trends, setTrends] = useState<TrendsData | null>(null);
  const [funnel, setFunnel] = useState<FunnelData | null>(null);

  useEffect(() => {
    const fetchAll = async () => {
      const [statsData, trendsData, funnelData] = await Promise.all([
        analyticsApi.getStats(),
        analyticsApi.getTrends(30),
        analyticsApi.getFunnel(),
      ]);
      
      setStats(statsData);
      setTrends(trendsData);
      setFunnel(funnelData);
    };

    fetchAll();
    const interval = setInterval(fetchAll, 5 * 60 * 1000); // refresh every 5 min
    return () => clearInterval(interval);
  }, []);

  if (!stats || !trends || !funnel) {
    return <div>Loading...</div>;
  }

  return (
    <div className="dashboard">
      <h1>Analytics Dashboard</h1>
      
      {/* KPI Cards */}
      <div className="stats-grid">
        <StatCard title="DAU" value={stats.dau} />
        <StatCard title="Completion Rate" value={`${stats.quiz_completion_rate}%`} />
        <StatCard title="Gift CTR" value={`${stats.gift_ctr}%`} />
        <StatCard title="Total Sessions" value={stats.total_sessions} />
      </div>

      {/* Trends Chart */}
      <TrendsChart data={trends} />

      {/* Funnel */}
      <FunnelChart data={funnel} />
    </div>
  );
};
```

## Important Notes

⚠️ **Cache:** Data is cached for 5-15 minutes. Don't poll more frequently.

⚠️ **Error Handling:** Always check for `error` field in response.

⚠️ **CORS:** Ensure your domain is whitelisted on backend.

⚠️ **Rate Limiting:** Max 60 requests/minute per IP (future).

## Event Names Reference

| Event | Description | When to track |
|-------|-------------|---------------|
| `quiz_started` | User began quiz | First question shown |
| `quiz_completed` | User finished quiz | Last question answered |
| `results_shown` | Results page displayed | Gift recommendations shown |
| `gift_clicked` | User clicked on gift | Click on product card |

## Support

📖 Full docs: `/docs/guides/analytics_frontend_integration.md`  
💬 Slack: `#gifty-backend`  
🐛 Issues: GitHub Issues
