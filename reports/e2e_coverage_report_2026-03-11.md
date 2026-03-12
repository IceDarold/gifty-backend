# E2E Coverage Report — Analytics Admin (2026-03-11)

## Scope
Target app: `apps/admin-tma`
Focus: analytics-related sections and live pipeline.

## Test Mapping (by file)

### Mock Suite
- `e2e/mock/analytics-dashboard-correctness.spec.ts`
  - Dashboard KPI cards and trends
  - Spider list + SpiderDetail (Overview, Categories)
  - Categories filter + pagination
- `e2e/mock/analytics-live-state.spec.ts`
  - Live snapshot modes: normal/empty/partial/out-of-order/duplicate
- `e2e/mock/analytics-intelligence.spec.ts`
  - Intelligence metrics correctness
  - Partial payload tolerance
  - Error fallback render
- `e2e/mock/analytics-llm-logs-matrix.spec.ts`
  - LLM Logs filters matrix
  - Pagination
  - Summary metrics correctness
  - Detail modal open
- `e2e/mock/analytics-logs-health.spec.ts`
  - Logs filter/apply + severity classification
  - Health normal state
  - Health degraded state
- `e2e/mock/analytics-ops-trends.spec.ts`
  - Ops tabs (Stats/Parsers/Categories/Queue/Workers/Scheduler)
  - Trend charts render
  - Queue lanes
  - Scheduler control
- `e2e/mock/analytics-negatives.spec.ts`
  - Unauthorized responses across analytics views
  - Slow responses stability
- `e2e/mock/navigation-and-core.spec.ts`
  - Top-level nav coverage
  - Logs filter/apply path
- `e2e/mock/operations-and-dashboard.spec.ts`
  - Dashboard/SpiderDetail
  - Operations tab smoke
  - Catalog search + pagination
- `e2e/mock/llm-and-intelligence.spec.ts`
  - LLM Logs basic flow
  - Intelligence basic flow
- `e2e/mock/frontend-and-settings.spec.ts`
  - Frontend control panel coverage
  - Settings runtime controls
  - Unauthorized banner checks

### Integration Suite
- `e2e/integration/live-analytics-smoke.spec.ts`
  - Live stack navigation (dashboard/logs/settings)
  - Snapshot endpoint contract
  - WS contract
- `e2e/integration/live-pipeline-e2e.spec.ts`
  - NATS publish → snapshot increment
  - WS message receipt
  - UI stability during live update

## Mock Suite Coverage (by section)

### Dashboard
- KPI cards: Active Spiders, Items Scraped, Discovery Rate, Latency
- Trends chart (DAU/Quiz)
- Spider list + SpiderDetail modal
- SpiderDetail tabs: Overview, Categories
- Categories pagination + filters

### Operations
- Tabs: Stats, Parsers, Categories, Queue, Workers, Scheduler
- Trends: items trend, tasks trend
- Queue lanes + run details entrypoints
- Scheduler controls

### Intelligence
- Cost metrics, tokens, requests
- Provider distribution
- Latency heatmap
- Error + partial payload fallbacks

### LLM Logs
- Filters matrix: provider, model, status, etc.
- Pagination
- Summary metrics (requests, cost, latency, tokens)
- Detail modal open
- Partial payload handling

### Logs
- Filter/apply path
- Severity classification

### Health
- Normal and degraded states

### Negative/Slow Paths
- Unauthorized (401) for analytics endpoints
- Slow responses stability

## Integration Suite Coverage (by section)

### Live Analytics Pipeline
- NATS publish → aggregator snapshot increment
- WS connectivity and message receipt
- UI stability during live updates

### Navigation Smoke
- Dashboard, Logs, Settings (live stack)
- Snapshot + WS contract

## Known Gaps (Not yet covered)
- Real WS reconnect scenario (forced drop + resubscribe)
- Dedup/out-of-order behavior in live integration (covered on mocks)
- Visual regressions/snapshots

## Test Entry Points
- Mock: `npm run test:e2e:mock`
- Integration: `npm run test:e2e:integration`
