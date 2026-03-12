import type { Page, Route } from "@playwright/test";
import { installMockWs } from "./mockWs";

type MockOptions = {
  liveSnapshotMode?: "normal" | "empty" | "partial" | "out_of_order" | "duplicate";
  intelligenceMode?: "full" | "empty" | "partial" | "error";
  llmLogsMode?: "full" | "empty" | "partial" | "error";
  opsMode?: "full" | "empty" | "partial" | "error";
  delayMs?: number;
  healthMode?: "normal" | "degraded";
  forceUnauthorized?: boolean;
};

type AppRow = { id: number; key: string; name: string; is_active: boolean };
type ReleaseRow = {
  id: number;
  app_id: number;
  version: string;
  target_url: string;
  status: string;
  health_status: string;
};
type ProfileRow = { id: number; key: string; name: string; is_active: boolean };
type RuleRow = {
  id: number;
  profile_id: number;
  priority: number;
  host_pattern: string;
  path_pattern: string;
  query_conditions: Record<string, string>;
  target_release_id: number;
  is_active: boolean;
};
type AllowedHostRow = { id: number; host: string; is_active: boolean };

type MockState = {
  apps: AppRow[];
  releases: ReleaseRow[];
  profiles: ProfileRow[];
  rules: RuleRow[];
  allowedHosts: AllowedHostRow[];
  auditLog: Array<{ id: number; action: string; entity_type: string; entity_id?: number; actor_id?: string; created_at: string }>;
  runtimeState: {
    active_profile_id?: number;
    fallback_release_id?: number;
    sticky_enabled?: boolean;
    sticky_ttl_seconds?: number;
    cache_ttl_seconds?: number;
  };
};

function nowIso() {
  return new Date().toISOString();
}

async function maybeDelay(route: Route, delayMs?: number) {
  if (!delayMs || delayMs <= 0) return;
  await new Promise((resolve) => setTimeout(resolve, delayMs));
}

function baseState(): MockState {
  return {
    apps: [{ id: 1, key: "product", name: "Main Product", is_active: true }],
    releases: [
      {
        id: 101,
        app_id: 1,
        version: "v1.0.0",
        target_url: "https://example.vercel.app",
        status: "ready",
        health_status: "healthy",
      },
    ],
    profiles: [{ id: 201, key: "main", name: "Main profile", is_active: true }],
    rules: [
      {
        id: 301,
        profile_id: 201,
        priority: 100,
        host_pattern: "*",
        path_pattern: "/*",
        query_conditions: {},
        target_release_id: 101,
        is_active: true,
      },
    ],
    allowedHosts: [{ id: 401, host: "example.vercel.app", is_active: true }],
    auditLog: [
      { id: 1, action: "seed", entity_type: "runtime", actor_id: "system", created_at: nowIso() },
    ],
    runtimeState: {
      active_profile_id: 201,
      fallback_release_id: 101,
      sticky_enabled: true,
      sticky_ttl_seconds: 1800,
      cache_ttl_seconds: 15,
    },
  };
}

async function bodyJson(route: Route) {
  try {
    return route.request().postDataJSON() as Record<string, any>;
  } catch {
    return {};
  }
}

function idFromPath(pathname: string): number | null {
  const match = pathname.match(/\/(\d+)(?:\/|$)/);
  if (!match) return null;
  return Number(match[1]);
}

export async function installMockApi(page: Page, opts: MockOptions = {}) {
  await installMockWs(page, opts);
  const state = baseState();
  let nextIds = { app: 2, release: 102, profile: 202, rule: 302, host: 402, audit: 2 };
  const updateWs = async (channel: string, data: any) => {
    try {
      await page.evaluate(
        ({ channel, data }) => {
          (window as any).__adminWsMockUpdate?.(channel, data);
        },
        { channel, data },
      );
    } catch {
      // ignore if page not ready
    }
  };

  await page.route("**/api/v1/**", async (route) => {
    const req = route.request();
    const method = req.method();
    const url = new URL(req.url());
    const path = url.pathname;

    await maybeDelay(route, opts.delayMs);

    if (opts.forceUnauthorized) {
      return route.fulfill({ status: 401, json: { detail: "unauthorized" } });
    }

    if (path.endsWith("/live-analytics/snapshot") && method === "GET") {
      if (opts.liveSnapshotMode === "empty") return route.fulfill({ json: { items: [] } });
      if (opts.liveSnapshotMode === "partial") return route.fulfill({ json: {} });
      if (opts.liveSnapshotMode === "out_of_order") {
        return route.fulfill({
          json: {
            items: [
              { channel: "global.kpi", seq: 9, data: { count: 20, sum: 40, min: 1, max: 9 } },
              { channel: "global.kpi", seq: 7, data: { count: 12, sum: 32, min: 1, max: 7 } },
            ],
          },
        });
      }
      if (opts.liveSnapshotMode === "duplicate") {
        return route.fulfill({
          json: {
            items: [
              { channel: "global.kpi", seq: 7, data: { count: 12, sum: 32, min: 1, max: 7 } },
              { channel: "global.kpi", seq: 7, data: { count: 12, sum: 32, min: 1, max: 7 } },
            ],
          },
        });
      }
      return route.fulfill({
        json: {
          items: [
            {
              channel: "global.kpi",
              seq: 7,
              data: {
                scope: "global",
                scope_key: "kpi",
                event_type: "kpi.quiz_started",
                count: 12,
                min: 1,
                max: 7,
                sum: 32,
                bucket_minute: "2026-03-11T09:00:00Z",
              },
            },
          ],
        },
      });
    }

    // Dashboard + generic.
    if (path.endsWith("/internal/stats") && method === "GET") {
      return route.fulfill({ json: { scraped_24h: 231, quiz_completion_rate: 42 } });
    }
    if (path.endsWith("/internal/health") && method === "GET") {
      if (opts.healthMode === "degraded") {
        return route.fulfill({
          json: {
            api: { status: "Degraded", latency: "920ms" },
            api_latency_ms: 920,
            database: { status: "Degraded", engine: "PostgreSQL" },
            redis: { status: "Degraded", memory_usage: "512MB" },
            rabbitmq: { status: "Degraded" },
          },
        });
      }
      return route.fulfill({
        json: {
          api: { status: "Healthy", latency: "11ms" },
          api_latency_ms: 111,
          database: { status: "Connected", engine: "PostgreSQL" },
          redis: { status: "Healthy", memory_usage: "14MB" },
          rabbitmq: { status: "Healthy" },
        },
      });
    }
    if (path.endsWith("/analytics/scraping") && method === "GET") {
      return route.fulfill({
        json: { completed: 12, failed: 1, running: 2, active_sources: 3, items_scraped_24h: 12345 },
      });
    }
    if (path.endsWith("/internal/sources") && method === "GET") {
      return route.fulfill({
        json: [
          { id: 10, site_key: "detmir", status: "idle", total_items: 120, type: "hub", merchant: "detmir", source_url: "https://detmir.ru" },
          { id: 11, site_key: "letu", status: "running", total_items: 220, type: "hub", merchant: "letu", source_url: "https://letu.ru" },
          {
            id: 12,
            site_key: "detmir",
            status: "waiting",
            total_items: 48,
            type: "list",
            merchant: "detmir",
            source_url: "https://detmir.ru/toys",
            last_synced_at: "2026-03-10T09:00:00Z",
            next_sync_at: "2026-03-12T09:00:00Z",
            is_active: true,
            config: { discovery_name: "Toys list" },
            url: "https://detmir.ru/toys",
          },
        ],
      });
    }
    if (path.endsWith("/internal/sources/backlog") && method === "GET") {
      return route.fulfill({ json: { items: [{ id: 51, source_id: 10, name: "toys" }], total: 1 } });
    }
    if (path.endsWith("/internal/sources/backlog/activate") && method === "POST") {
      return route.fulfill({ json: { activated: 1 } });
    }
    if (path.endsWith("/internal/sources/sync-spiders") && method === "POST") {
      return route.fulfill({ json: { synced: true } });
    }
    if (path.endsWith("/internal/sources/run-all") && method === "POST") {
      return route.fulfill({ json: { accepted: true } });
    }
    if (/\/internal\/sources\/\d+\/force-run$/.test(path) && method === "POST") {
      return route.fulfill({ json: { accepted: true } });
    }
    if (/\/internal\/sources\/\d+$/.test(path) && method === "PATCH") {
      return route.fulfill({ json: { status: "ok" } });
    }
    if (/\/internal\/sources\/\d+\/data$/.test(path) && method === "DELETE") {
      return route.fulfill({ json: { deleted: true } });
    }
    if (/\/internal\/sources\/\d+\/products$/.test(path) && method === "GET") {
      return route.fulfill({ json: { items: [], total: 0 } });
    }

    if (path.endsWith("/analytics/trends") && method === "GET") {
      return route.fulfill({
        json: [
          { name: "03/09", dau: 12, completed: 22 },
          { name: "03/10", dau: 14, completed: 24 },
          { name: "03/11", dau: 16, completed: 30 },
        ],
      });
    }

    if (path.endsWith("/internal/workers") && method === "GET") {
      return route.fulfill({ json: [{ hostname: "w1", cpu_usage_pct: 22, ram_usage_pct: 35, concurrent_tasks: 2 }] });
    }
    if (path.endsWith("/internal/queues/stats") && method === "GET") {
      return route.fulfill({ json: { messages_total: 4, messages_ready: 1, messages_unacknowledged: 1 } });
    }
    if (path.endsWith("/internal/queues/tasks") && method === "GET") {
      return route.fulfill({ json: { items: [{ id: 1, task: "run_spider", status: "queued" }] } });
    }
    if (path.endsWith("/internal/queues/history") && method === "GET") {
      return route.fulfill({ json: { items: [{ run_id: 9001, status: "completed", source_id: 10 }], total: 1 } });
    }

    // Catalog.
    if (path.endsWith("/internal/products") && method === "GET") {
      const q = (url.searchParams.get("search") || "").toLowerCase();
      const items = [
        {
          product_id: 1,
          title: "Lego Set",
          merchant: "detmir",
          category: "toys",
          price: 1299,
          currency: "RUB",
          product_url: "https://example.com/lego",
          image_url: "",
        },
        {
          product_id: 2,
          title: "Perfume Gift",
          merchant: "letu",
          category: "beauty",
          price: 2499,
          currency: "RUB",
          product_url: "https://example.com/perfume",
          image_url: "",
        },
      ].filter((x) => (q ? x.title.toLowerCase().includes(q) : true));
      return route.fulfill({ json: { items, total: items.length } });
    }

    // Intelligence.
    if (path.endsWith("/internal/analytics/intelligence") && method === "GET") {
      if (opts.intelligenceMode === "error") {
        return route.fulfill({ status: 500, json: { detail: "error" } });
      }
      if (opts.intelligenceMode === "empty") {
        return route.fulfill({ json: { metrics: {}, providers: [], latency_heatmap: [] } });
      }
      if (opts.intelligenceMode === "partial") {
        return route.fulfill({ json: { metrics: { total_cost: 1.7 }, providers: [], latency_heatmap: [] } });
      }
      return route.fulfill({
        json: {
          metrics: { total_cost: 1.7, total_tokens: 12345, total_requests: 88 },
          providers: [{ provider: "anthropic", count: 40 }],
          latency_heatmap: [{ hour: 9, avg_latency: 900 }],
        },
      });
    }

    // LLM logs.
    if (path.endsWith("/internal/analytics/llm/logs") && method === "GET") {
      if (opts.llmLogsMode === "error") {
        return route.fulfill({ status: 500, json: { detail: "error" } });
      }
      if (opts.llmLogsMode === "empty") {
        return route.fulfill({ json: { items: [], has_more: false, next_cursor: null } });
      }
      if (opts.llmLogsMode === "partial") {
        return route.fulfill({ json: { items: [{ id: "log_partial", provider: "anthropic" }], has_more: false, next_cursor: null } });
      }
      const provider = url.searchParams.get("provider") || "anthropic";
      const model = url.searchParams.get("model") || "claude-3-haiku";
      const status = url.searchParams.get("status") || "ok";
      const cursor = url.searchParams.get("cursor") || "";
      const id = cursor ? "log_2" : "log_1";
      return route.fulfill({
        json: {
          items: [
            {
              id,
              provider,
              model,
              call_type: "normalize_topics",
              status,
              total_tokens: 123,
              latency_ms: 210,
              cost_usd: 0.004,
              created_at: "2026-03-11T09:00:00Z",
              usage_captured: true,
              provider_request_captured: true,
              provider_request_id: cursor ? "req_2" : "req_1",
            },
          ],
          has_more: !cursor,
          next_cursor: cursor ? null : "cursor_1",
        },
      });
    }
    if (path.endsWith("/internal/analytics/llm/throughput") && method === "GET") {
      return route.fulfill({ json: { points: [{ ts: "2026-03-11T09:00:00Z", count: 3 }] } });
    }
    if (path.endsWith("/internal/analytics/llm/stats") && method === "GET") {
      return route.fulfill({
        json: {
          total: 1,
          errors: 0,
          error_rate: 0,
          total_cost_usd: 0.004,
          avg_cost_usd: 0.004,
          p95_latency_ms: 210,
          p50_latency_ms: 210,
          avg_latency_ms: 210,
          p95_total_tokens: 123,
          p50_total_tokens: 123,
          avg_total_tokens: 123,
          missing_usage_count: 0,
          missing_provider_request_id_count: 0,
        },
      });
    }
    if (path.endsWith("/internal/analytics/llm/outliers") && method === "GET") {
      return route.fulfill({
        json: { items: [{ id: "log_1", provider: "anthropic", model: "claude-3-haiku", call_type: "normalize_topics", status: "ok", latency_ms: 210, total_tokens: 123, cost_usd: 0.004, created_at: "2026-03-11T09:00:00Z" }] },
      });
    }
    if (path.endsWith("/internal/analytics/llm/breakdown") && method === "GET") {
      const groupBy = url.searchParams.get("group_by") || "status";
      return route.fulfill({ json: { items: [{ key: groupBy === "status" ? "ok" : "anthropic", requests: 1 }] } });
    }
    if (/\/internal\/analytics\/llm\/logs\/.+/.test(path) && method === "GET") {
      return route.fulfill({
        json: {
          id: "log_1",
          provider: "anthropic",
          model: "claude-3-haiku",
          status: "ok",
          request_payload: { prompt: "hi" },
          response_payload: { text: "hello" },
          raw_response: { id: "raw_1" },
        },
      });
    }

    // Logs.
    if (path.endsWith("/internal/logs/services") && method === "GET") {
      return route.fulfill({ json: { items: ["api", "scraper", "scheduler"] } });
    }
    if (path.endsWith("/internal/logs/query") && method === "GET") {
      const q = url.searchParams.get("q") || "";
      return route.fulfill({
        json: {
          items: [
            { ts: "2026-03-11T09:01:00Z", ts_ns: 1, service: "api", line: q ? `filtered ${q}` : "hello world" },
            { ts: "2026-03-11T09:02:00Z", ts_ns: 2, service: "api", line: "request processed" },
          ],
        },
      });
    }

    // Settings.
    if (/\/internal\/subscribers\/\d+$/.test(path) && method === "GET") {
      return route.fulfill({ json: { subscriptions: ["global"], language: "en" } });
    }
    if (/\/internal\/subscribers\/\d+\/(subscribe|unsubscribe|language)$/.test(path) && method === "POST") {
      return route.fulfill({ json: { ok: true } });
    }
    if (path.endsWith("/internal/telegram/test-notification") && method === "POST") {
      return route.fulfill({ json: { sent: true } });
    }
    if (path.endsWith("/internal/weeek/connect") && method === "POST") {
      return route.fulfill({ json: { connected: true } });
    }
    if (path.endsWith("/internal/ops/runtime-settings") && method === "GET") {
      return route.fulfill({
        json: {
          item: {
            settings_version: 1,
            ops_aggregator_enabled: true,
            ops_aggregator_interval_ms: 2000,
            ops_snapshot_ttl_ms: 10000,
            ops_stale_max_age_ms: 60000,
            ops_client_intervals: { "dashboard.stats_ms": 30000, "dashboard.health_ms": 30000 },
            bounds: {
              ops_aggregator_interval_ms: { min: 500, max: 60000 },
              ops_snapshot_ttl_ms: { min: 1000, max: 300000 },
              ops_stale_max_age_ms: { min: 5000, max: 600000 },
              ops_client_intervals: { min: 1000, max: 600000 },
            },
          },
        },
      });
    }
    if (path.endsWith("/internal/ops/runtime-settings") && (method === "PUT" || method === "PATCH")) {
      const payload = await bodyJson(route);
      const item = {
        settings_version: 1,
        ops_aggregator_enabled: true,
        ops_aggregator_interval_ms: 2000,
        ops_snapshot_ttl_ms: 10000,
        ops_stale_max_age_ms: 60000,
        ops_client_intervals: { "dashboard.stats_ms": 30000, "dashboard.health_ms": 30000 },
        bounds: {
          ops_aggregator_interval_ms: { min: 500, max: 60000 },
          ops_snapshot_ttl_ms: { min: 1000, max: 300000 },
          ops_stale_max_age_ms: { min: 5000, max: 600000 },
          ops_client_intervals: { min: 1000, max: 600000 },
        },
        ...payload,
      };
      await updateWs("settings.runtime", { item });
      return route.fulfill({ json: { status: "ok", item } });
    }
    if (path.endsWith("/internal/merchants") && method === "GET") {
      return route.fulfill({ json: { items: [{ site_key: "detmir", name: "Detmir", base_url: "https://detmir.ru" }], total: 1 } });
    }
    if (/\/internal\/merchants\/.+/.test(path) && method === "PATCH") {
      return route.fulfill({ json: { ok: true } });
    }

    // Ops.
    if (path.endsWith("/internal/ops/overview") && method === "GET") {
      if (opts.opsMode === "error") return route.fulfill({ status: 500, json: { detail: "error" } });
      if (opts.opsMode === "empty") return route.fulfill({ json: {} });
      return route.fulfill({
        json: {
          queue: { messages_total: 3, messages_ready: 1, messages_unacknowledged: 1 },
          runs: { running: 1, completed: 10, error: 1 },
          workers: {
            online: 1,
            items: [{ hostname: "w1", pid: 1, status: "running", concurrent_tasks: 1, ram_usage_pct: 20, paused: false, active_tasks: [] }],
          },
          discovery_categories: { new: 2, promoted: 1, rejected: 0, inactive: 0 },
          discovery_products: { total: 500 },
        },
      });
    }
    if (path.endsWith("/internal/ops/sites") && method === "GET") {
      if (opts.opsMode === "empty") return route.fulfill({ json: { items: [] } });
      return route.fulfill({
        json: {
          items: [
            {
              site_key: "detmir",
              name: "Detmir",
              runtime_hub_source_id: 10,
              counters: {
                discovered_new: 2,
                discovered_promoted: 1,
                discovered_rejected: 0,
                discovered_inactive: 0,
                discovered_total: 3,
                running: 1,
                active: 3,
              },
              workers: [{ worker_id: "w1:1", status: "running", tasks: 1 }],
            },
          ],
        },
      });
    }
    if (/\/internal\/ops\/sites\/.+\/pipeline$/.test(path) && method === "GET") {
      return route.fulfill({ json: { items: [{ source_id: 10, source_name: "Detmir hub", run_status: "idle", is_active: true }] } });
    }
    if (path.endsWith("/internal/ops/runs/active") && method === "GET") {
      if (opts.opsMode === "empty") return route.fulfill({ json: { items: [] } });
      return route.fulfill({ json: { items: [{ run_id: 9001, source_id: 10, site_key: "detmir", status: "running", created_at: nowIso(), updated_at: nowIso() }] } });
    }
    if (path.endsWith("/internal/ops/runs/queued") && method === "GET") {
      if (opts.opsMode === "empty") return route.fulfill({ json: { items: [], total: 0 } });
      return route.fulfill({ json: { items: [{ run_id: 9002, source_id: 10, site_key: "detmir", status: "queued", created_at: nowIso(), updated_at: nowIso() }], total: 1 } });
    }
    if (/\/internal\/ops\/runs\/\d+$/.test(path) && method === "GET") {
      const runId = idFromPath(path) ?? 9001;
      return route.fulfill({
        json: {
          item: {
            run_id: runId,
            source_id: 10,
            run_status: "running",
            created_at: nowIso(),
            updated_at: nowIso(),
            timeline: [{ status: "queued", at: nowIso() }, { status: "running", at: nowIso() }],
            logs: "step 1\nstep 2",
            logs_meta: { chars: 12, lines: 2 },
          },
        },
      });
    }
    if (/\/internal\/ops\/runs\/\d+\/retry$/.test(path) && method === "POST") {
      return route.fulfill({ json: { accepted: true } });
    }
    if (path.endsWith("/internal/ops/scheduler/stats") && method === "GET") {
      return route.fulfill({
        json: {
          summary: { scheduler_paused: false, tasks_planned: 10, tasks_completed: 8, tasks_failed: 1, queue_size: 2 },
          timeline: [{ ts: nowIso(), queued: 2, planned: 3, completed: 2 }],
        },
      });
    }
    if (path.endsWith("/internal/ops/tasks-trend") && method === "GET") {
      return route.fulfill({ json: { items: [{ date: "2026-03-10", queued: 3, running: 2, success: 5, error: 1 }], totals: { queue_max: 3, running_max: 2, success: 5, error: 1 } } });
    }
    if (path.endsWith("/internal/ops/items-trend") && method === "GET") {
      return route.fulfill({ json: { items: [{ date: "2026-03-10", items_new: 12, categories_new: 3 }], totals: { items_new: 12, categories_new: 3 } } });
    }
    if (path.endsWith("/internal/ops/discovery/categories") && method === "GET") {
      return route.fulfill({
        json: {
          items: [
            { id: 501, source_id: 10, source_name: "detmir", category_name: "toys", state: "new", products_count: 12 },
            { id: 502, source_id: 10, source_name: "detmir", category_name: "board games", state: "promoted", products_count: 7 },
          ],
          total: 2,
        },
      });
    }
    if (/\/internal\/ops\/discovery\/(promote|reject|reactivate)$/.test(path) && method === "POST") {
      return route.fulfill({ json: { ok: true } });
    }
    if (path.endsWith("/internal/ops/sources/bulk-update") && method === "POST") {
      return route.fulfill({ json: { updated: 1 } });
    }
    if (/\/internal\/ops\/sites\/.+\/run-discovery$/.test(path) && method === "POST") {
      return route.fulfill({ json: { accepted: true } });
    }
    if (/\/internal\/ops\/workers\/.+\/(pause|resume)$/.test(path) && method === "POST") {
      return route.fulfill({ json: { ok: true } });
    }
    if (/\/internal\/ops\/scheduler\/(pause|resume)$/.test(path) && method === "POST") {
      return route.fulfill({ json: { ok: true } });
    }

    // Frontend control panel (stateful).
    if (path.endsWith("/internal/frontend/apps") && method === "GET") return route.fulfill({ json: { items: state.apps } });
    if (path.endsWith("/internal/frontend/releases") && method === "GET") return route.fulfill({ json: { items: state.releases } });
    if (path.endsWith("/internal/frontend/profiles") && method === "GET") return route.fulfill({ json: { items: state.profiles } });
    if (path.endsWith("/internal/frontend/rules") && method === "GET") return route.fulfill({ json: { items: state.rules } });
    if (path.endsWith("/internal/frontend/runtime-state") && method === "GET") return route.fulfill({ json: { item: state.runtimeState } });
    if (path.endsWith("/internal/frontend/allowed-hosts") && method === "GET") return route.fulfill({ json: { items: state.allowedHosts } });
    if (path.endsWith("/internal/frontend/audit-log") && method === "GET") return route.fulfill({ json: { items: state.auditLog } });

    if (path.endsWith("/internal/frontend/apps") && method === "POST") {
      const payload = await bodyJson(route);
      const app: AppRow = { id: nextIds.app++, key: String(payload.key || "app"), name: String(payload.name || "App"), is_active: payload.is_active !== false };
      state.apps.push(app);
      state.auditLog.unshift({ id: nextIds.audit++, action: "create", entity_type: "app", entity_id: app.id, actor_id: "e2e", created_at: nowIso() });
      await updateWs("frontend.apps", { items: state.apps });
      await updateWs("frontend.audit_log", { items: state.auditLog });
      return route.fulfill({ json: app });
    }
    if (/\/internal\/frontend\/apps\/\d+$/.test(path) && method === "DELETE") {
      const id = idFromPath(path);
      state.apps = state.apps.filter((x) => x.id !== id);
      state.auditLog.unshift({ id: nextIds.audit++, action: "delete", entity_type: "app", entity_id: id || undefined, actor_id: "e2e", created_at: nowIso() });
      await updateWs("frontend.apps", { items: state.apps });
      await updateWs("frontend.audit_log", { items: state.auditLog });
      return route.fulfill({ json: { ok: true } });
    }

    if (path.endsWith("/internal/frontend/releases") && method === "POST") {
      const payload = await bodyJson(route);
      const release: ReleaseRow = {
        id: nextIds.release++,
        app_id: Number(payload.app_id || state.apps[0]?.id || 1),
        version: String(payload.version || "v-new"),
        target_url: String(payload.target_url || "https://example.vercel.app"),
        status: String(payload.status || "draft"),
        health_status: "unknown",
      };
      state.releases.push(release);
      return route.fulfill({ json: release });
    }
    if (/\/internal\/frontend\/releases\/\d+\/validate$/.test(path) && method === "POST") {
      return route.fulfill({ json: { ok: true, status_code: 200 } });
    }
    if (/\/internal\/frontend\/releases\/\d+$/.test(path) && method === "DELETE") {
      const id = idFromPath(path);
      state.releases = state.releases.filter((x) => x.id !== id);
      return route.fulfill({ json: { ok: true } });
    }

    if (path.endsWith("/internal/frontend/profiles") && method === "POST") {
      const payload = await bodyJson(route);
      const profile: ProfileRow = { id: nextIds.profile++, key: String(payload.key || "profile"), name: String(payload.name || "Profile"), is_active: payload.is_active !== false };
      state.profiles.push(profile);
      return route.fulfill({ json: profile });
    }

    if (path.endsWith("/internal/frontend/rules") && method === "POST") {
      const payload = await bodyJson(route);
      const rule: RuleRow = {
        id: nextIds.rule++,
        profile_id: Number(payload.profile_id || state.profiles[0]?.id || 201),
        priority: Number(payload.priority || 100),
        host_pattern: String(payload.host_pattern || "*"),
        path_pattern: String(payload.path_pattern || "/*"),
        query_conditions: (payload.query_conditions as Record<string, string>) || {},
        target_release_id: Number(payload.target_release_id || state.releases[0]?.id || 101),
        is_active: payload.is_active !== false,
      };
      state.rules.push(rule);
      return route.fulfill({ json: rule });
    }
    if (/\/internal\/frontend\/rules\/\d+$/.test(path) && method === "DELETE") {
      const id = idFromPath(path);
      state.rules = state.rules.filter((x) => x.id !== id);
      return route.fulfill({ json: { ok: true } });
    }

    if (path.endsWith("/internal/frontend/runtime-state") && method === "POST") {
      const payload = await bodyJson(route);
      state.runtimeState = { ...state.runtimeState, ...payload };
      return route.fulfill({ json: { ok: true, item: state.runtimeState } });
    }

    if (path.endsWith("/internal/frontend/allowed-hosts") && method === "POST") {
      const payload = await bodyJson(route);
      const host: AllowedHostRow = { id: nextIds.host++, host: String(payload.host || "example.vercel.app"), is_active: payload.is_active !== false };
      state.allowedHosts.push(host);
      state.auditLog.unshift({ id: nextIds.audit++, action: "create", entity_type: "host", entity_id: host.id, actor_id: "e2e", created_at: nowIso() });
      await updateWs("frontend.allowed_hosts", { items: state.allowedHosts });
      await updateWs("frontend.audit_log", { items: state.auditLog });
      return route.fulfill({ json: host });
    }
    if (/\/internal\/frontend\/allowed-hosts\/\d+$/.test(path) && method === "DELETE") {
      const id = idFromPath(path);
      state.allowedHosts = state.allowedHosts.filter((x) => x.id !== id);
      state.auditLog.unshift({ id: nextIds.audit++, action: "delete", entity_type: "host", entity_id: id || undefined, actor_id: "e2e", created_at: nowIso() });
      await updateWs("frontend.allowed_hosts", { items: state.allowedHosts });
      await updateWs("frontend.audit_log", { items: state.auditLog });
      return route.fulfill({ json: { ok: true } });
    }

    if (path.endsWith("/internal/frontend/publish") && method === "POST") {
      const payload = await bodyJson(route);
      state.runtimeState = {
        ...state.runtimeState,
        active_profile_id: Number(payload.active_profile_id || state.runtimeState.active_profile_id),
        fallback_release_id: Number(payload.fallback_release_id || state.runtimeState.fallback_release_id),
        sticky_enabled: payload.sticky_enabled ?? state.runtimeState.sticky_enabled,
        sticky_ttl_seconds: Number(payload.sticky_ttl_seconds || state.runtimeState.sticky_ttl_seconds || 1800),
        cache_ttl_seconds: Number(payload.cache_ttl_seconds || state.runtimeState.cache_ttl_seconds || 15),
      };
      state.auditLog.unshift({ id: nextIds.audit++, action: "publish", entity_type: "runtime", actor_id: "e2e", created_at: nowIso() });
      await updateWs("frontend.runtime_state", { item: state.runtimeState });
      await updateWs("frontend.audit_log", { items: state.auditLog });
      return route.fulfill({ json: { status: "ok" } });
    }
    if (path.endsWith("/internal/frontend/rollback") && method === "POST") {
      state.auditLog.unshift({ id: nextIds.audit++, action: "rollback", entity_type: "runtime", actor_id: "e2e", created_at: nowIso() });
      await updateWs("frontend.audit_log", { items: state.auditLog });
      return route.fulfill({ json: { status: "ok" } });
    }

    return route.fulfill({ json: {} });
  });
}
