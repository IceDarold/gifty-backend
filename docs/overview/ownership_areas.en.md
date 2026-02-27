# Ownership Areas (2 Domains)

This doc is meant to help you **delegate full ownership** of large project areas to strong engineers.
We split by **outcomes** (reliability, speed, data quality, UX) rather than by services.

---

## Domain A: Parsing Platform

**Mission:** guarantee a stable and controllable pipeline *category → queue → run → ingestion → correct DB state*.

### Ownership scope
- Execution: RabbitMQ, workers, scheduler, retries/backoff, rate limiting, backpressure.
- Data correctness: schemas, migrations, deduplication, invariants/consistency.
- Observability: metrics, logs, diagnostics, auto-remediation (e.g. auto-disable broken).
- Parsing integrations: scrapy pipeline → `api/v1/internal/ingest-batch`.

### What “Done” means
- If the queue has tasks, workers are not “idle” without a clear diagnosis.
- A run cannot be `completed` if ingestion actually failed (status/logs are consistent).
- Re-running categories correctly enriches product provenance (category links).

### Core entities (DB)
- `parsing_hubs`
- `discovered_categories`
- `parsing_sources`
- `parsing_runs`
- `product_category_links` (site category provenance)
- `merchants` (store metadata; key = `site_key`)
- RabbitMQ queue: `parsing_tasks` (source of truth for “In queue”)

### Core internal APIs
- `/api/v1/internal/ops/*`
- `/api/v1/internal/queues/*`
- `/api/v1/internal/ingest-batch`

### KPIs / SLOs (examples)
- Run success rate (%)
- Queue lag (ready/unacked, wait time)
- Throughput (new products/min, total products/min)
- MTTR
- Data quality: share of products missing `product_category_links` after re-runs

---

## Domain B: Operations & Admin UX

**Mission:** make Operations Center an “operator workspace” — fast, clear, realtime, minimal noise.

### Ownership scope
- UX & workflow: how users manage parsers/categories/queue and understand system state.
- Realtime: SSE, snapshot versions, reduce polling.
- Error UX: clear 500/403/timeouts, retries, max attempts.
- Global Catalog UX: search/pagination, scraped category display, “n new items” banners.
- Runtime settings: global refresh intervals and performance knobs.

### What “Done” means
- UI does not pull megabytes of duplicate data in loops.
- On API errors users see a clear message + retry button (no infinite requests).
- Long-running actions have feedback: pending → success/error + result.

### Key interfaces
- `apps/admin-tma` (Next.js / TMA)
- Internal API contracts (`/api/v1/internal/ops/*`, `/api/v1/internal/products`, `/api/v1/internal/merchants`)
- SSE: `/api/v1/internal/ops/stream`

### KPIs / SLOs (examples)
- Time-to-action (open → start discovery/run)
- UI update latency after events
- API calls per user (min)
- Crash-free sessions / no hydration errors

---

## Domain boundaries

**Parsing Platform owner** owns:
- run truthfulness and final statuses
- queue/workers/scheduler
- parsing/ingestion data models and tables

**Operations/Admin owner** owns:
- how those states/actions are represented in UI
- frontend performance and request noise
- additive internal API response contracts needed by UI

Rule of thumb:
- “what is true in the system” → Domain A
- “how operators see/control it” → Domain B

---

## Cadence
- Each domain has an owner and a backup.
- Weekly 30-min sync: what broke, what got faster, what got automated.
- Owners can ship changes in their area; breaking API/DB changes get a quick cross-review.

---

## First 30 days (starter backlog)

### Domain A
- Add metrics: queue lag, worker utilization, ingest latency.
- Enforce invariant: “ingest error => run error”.
- Improve `product_category_links` provenance + add ingestion tests.

### Domain B
- Reduce polling (SSE + version-driven refresh).
- Standardize error UI + retry (max 2 attempts) everywhere.
- Make Catalog UX solid: scraped category, merchants admin, fast filters.

