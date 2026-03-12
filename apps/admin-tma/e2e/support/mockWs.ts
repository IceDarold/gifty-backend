import type { Page } from "@playwright/test";

type MockOptions = {
  liveSnapshotMode?: "normal" | "empty" | "partial" | "out_of_order" | "duplicate";
  intelligenceMode?: "full" | "empty" | "partial" | "error";
  llmLogsMode?: "full" | "empty" | "partial" | "error";
  opsMode?: "full" | "empty" | "partial" | "error";
  delayMs?: number;
  healthMode?: "normal" | "degraded";
  forceUnauthorized?: boolean;
};

type MockWsState = {
  mode: Required<MockOptions>["liveSnapshotMode"];
  forceUnauthorized: boolean;
  channels: Record<string, any>;
};

function nowIso() {
  return new Date().toISOString();
}

function buildMockWsState(opts: MockOptions = {}): MockWsState {
  const mode = opts.liveSnapshotMode || "normal";
  const forceUnauthorized = !!opts.forceUnauthorized;
  const health =
    opts.healthMode === "degraded"
      ? {
          api: { status: "Degraded", latency: "920ms" },
          api_latency_ms: 920,
          database: { status: "Degraded", engine: "PostgreSQL" },
          redis: { status: "Degraded", memory_usage: "512MB" },
          rabbitmq: { status: "Degraded" },
        }
      : {
          api: { status: "Healthy", latency: "11ms" },
          api_latency_ms: 111,
          database: { status: "Connected", engine: "PostgreSQL" },
          redis: { status: "Healthy", memory_usage: "14MB" },
          rabbitmq: { status: "Healthy" },
        };

  const intelligence =
    opts.intelligenceMode === "error"
      ? undefined
      : opts.intelligenceMode === "empty"
        ? { metrics: {}, providers: [], latency_heatmap: [] }
        : opts.intelligenceMode === "partial"
          ? { metrics: { total_cost: 1.7 }, providers: [], latency_heatmap: [] }
          : {
              metrics: { total_cost: 1.7, total_tokens: 12345, total_requests: 88 },
              providers: [{ provider: "anthropic", count: 40 }],
              latency_heatmap: [{ hour: 9, avg_latency: 900 }],
            };

  const llmLogsFull = [
    {
      id: "log_1",
      provider: "groq",
      model: "gemma",
      call_type: "normalize_topics",
      status: "error",
      latency_ms: 210,
      total_tokens: 123,
      cost_usd: 0.004,
      created_at: "2026-03-11T09:00:00Z",
    },
    {
      id: "log_2",
      provider: "anthropic",
      model: "claude-3-haiku",
      call_type: "normalize_topics",
      status: "ok",
      latency_ms: 120,
      total_tokens: 80,
      cost_usd: 0.003,
      created_at: "2026-03-11T09:01:00Z",
    },
  ];
  const llmLogsPartial = [
    {
      id: "log_partial",
      provider: "groq",
      model: "",
      call_type: "normalize_topics",
      status: "ok",
      latency_ms: 0,
      total_tokens: 0,
      cost_usd: 0,
      created_at: "2026-03-11T09:05:00Z",
    },
  ];
  const llmLogs =
    opts.llmLogsMode === "empty"
      ? []
      : opts.llmLogsMode === "partial"
        ? llmLogsPartial
        : llmLogsFull;

  const llmStats =
    opts.llmLogsMode === "empty"
      ? {
          total: 0,
          errors: 0,
          error_rate: 0,
          total_cost_usd: 0,
          avg_cost_usd: 0,
          p95_latency_ms: 0,
          p50_latency_ms: 0,
          avg_latency_ms: 0,
          p95_total_tokens: 0,
          p50_total_tokens: 0,
          avg_total_tokens: 0,
          missing_usage_count: 0,
          missing_provider_request_id_count: 0,
        }
      : {
          total: llmLogs.length,
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
        };

  return {
    mode,
    forceUnauthorized,
    channels: {
      "dashboard.stats": { quiz_completion_rate: 42 },
      "dashboard.health": health,
      "dashboard.scraping": { completed: 12, failed: 1, running: 2, active_sources: 3, items_scraped_24h: 12345 },
      "dashboard.sources": [
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
      "dashboard.trends": [
        { name: "03/09", dau: 12, completed: 22 },
        { name: "03/10", dau: 14, completed: 24 },
        { name: "03/11", dau: 16, completed: 30 },
      ],
      "dashboard.workers": [{ hostname: "w1", cpu_usage_pct: 22, ram_usage_pct: 35, concurrent_tasks: 2 }],
      "dashboard.queue": { messages_total: 4, messages_ready: 1, messages_unacknowledged: 1 },
      "dashboard.discovered_categories": { items: [{ id: 51, source_id: 10, name: "toys" }], total: 1 },

      "ops.overview":
        opts.opsMode === "empty"
          ? {}
          : {
              queue: { messages_total: 3, messages_ready: 1, messages_unacknowledged: 1 },
              runs: { running: 1, completed: 10, error: 1 },
              workers: {
                online: 1,
                items: [{ hostname: "w1", pid: 1, status: "running", concurrent_tasks: 1, ram_usage_pct: 20, paused: false, active_tasks: [] }],
              },
              discovery_categories: { new: 2, promoted: 1, rejected: 0, inactive: 0 },
              discovery_products: { total: 500 },
            },
      "ops.sites":
        opts.opsMode === "empty"
          ? { items: [] }
          : {
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
      "ops.pipeline": { detmir: { items: [{ source_id: 10, source_name: "Detmir hub", run_status: "idle", is_active: true }] } },
      "ops.scheduler_stats": {
        summary: { scheduler_paused: false, tasks_planned: 10, tasks_completed: 8, tasks_failed: 1, queue_size: 2 },
        timeline: [{ ts: nowIso(), queued: 2, planned: 3, completed: 2 }],
      },
      "ops.items_trend": {
        week: { items: [{ date: "2026-03-10", items_new: 12, categories_new: 3 }], totals: { items_new: 12, categories_new: 3 } },
        day: { items: [{ date: "2026-03-10", items_new: 12, categories_new: 3 }], totals: { items_new: 12, categories_new: 3 } },
        hour: { items: [{ date: "2026-03-10", items_new: 12, categories_new: 3 }], totals: { items_new: 12, categories_new: 3 } },
        minute: { items: [{ date: "2026-03-10", items_new: 12, categories_new: 3 }], totals: { items_new: 12, categories_new: 3 } },
      },
      "ops.tasks_trend": {
        week: { items: [{ date: "2026-03-10", queued: 3, running: 2, success: 5, error: 1 }], totals: { queue_max: 3, running_max: 2, success: 5, error: 1 } },
        day: { items: [{ date: "2026-03-10", queued: 3, running: 2, success: 5, error: 1 }], totals: { queue_max: 3, running_max: 2, success: 5, error: 1 } },
        hour: { items: [{ date: "2026-03-10", queued: 3, running: 2, success: 5, error: 1 }], totals: { queue_max: 3, running_max: 2, success: 5, error: 1 } },
        minute: { items: [{ date: "2026-03-10", queued: 3, running: 2, success: 5, error: 1 }], totals: { queue_max: 3, running_max: 2, success: 5, error: 1 } },
      },
      "ops.discovery": {
        items: [
          { id: 501, source_id: 10, source_name: "detmir", category_name: "toys", state: "new", products_count: 12 },
          { id: 502, source_id: 10, source_name: "detmir", category_name: "board games", state: "promoted", products_count: 7 },
        ],
        total: 2,
      },
      "ops.runs.active": { items: [{ run_id: 9001, source_id: 10, site_key: "detmir", status: "running", created_at: nowIso(), updated_at: nowIso() }] },
      "ops.runs.queued": { items: [{ run_id: 9002, source_id: 10, site_key: "detmir", status: "queued", created_at: nowIso(), updated_at: nowIso() }], total: 1 },
      "ops.runs.completed": { items: [{ run_id: 9003, status: "completed", source_id: 10 }] },
      "ops.runs.error": { items: [{ run_id: 9004, status: "error", source_id: 10 }] },
      "ops.run_details": {},

      "intelligence.summary": intelligence,

      "llm.logs": { items: llmLogs },
      "llm.stats": llmStats,
      "llm.throughput": { points: [{ ts: "2026-03-11T09:00:00Z", count: 3 }] },
      "llm.outliers": {
        items: [{ id: "log_1", provider: "anthropic", model: "claude-3-haiku", call_type: "normalize_topics", status: "ok", latency_ms: 210, total_tokens: 123, cost_usd: 0.004, created_at: "2026-03-11T09:00:00Z" }],
      },
      "llm.breakdown.status": { items: [{ key: "ok", requests: 1 }] },
      "llm.breakdown.provider": { items: [{ key: "anthropic", requests: 1, total_cost_usd: 0.004, total_tokens: 123 }] },
      "llm.breakdown.model": { items: [{ key: "claude-3-haiku", requests: 1, total_cost_usd: 0.004, avg_latency_ms: 210 }] },
      "llm.breakdown.call_type": { items: [{ key: "normalize_topics", requests: 1, total_cost_usd: 0.004, total_tokens: 123 }] },

      "logs.services": { items: ["api", "scraper", "scheduler"] },
      "logs.snapshot": {
        items: [
          { ts: "2026-03-11T09:01:00Z", ts_ns: 1, service: "api", line: "hello world" },
          { ts: "2026-03-11T09:02:00Z", ts_ns: 2, service: "api", line: "filtered error: request processed" },
        ],
      },
      "logs.tail": {
        items: [
          { ts: "2026-03-11T09:03:00Z", ts_ns: 3, service: "api", line: "tail line" },
          { ts: "2026-03-11T09:03:30Z", ts_ns: 4, service: "api", line: "filtered error: failed" },
        ],
      },

      "catalog.products": {
        items: [
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
        ],
        total: 2,
      },
      "settings.runtime": {
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
      "settings.merchants": { items: [{ site_key: "detmir", name: "Detmir", base_url: "https://detmir.ru" }], total: 1 },
      "settings.subscriber": { subscriptions: ["global"], language: "en" },

      "frontend.apps": { items: [{ id: 1, key: "product", name: "Main Product", is_active: true }] },
      "frontend.releases": { items: [{ id: 101, app_id: 1, version: "v1.0.0", target_url: "https://example.vercel.app", status: "ready", health_status: "healthy" }] },
      "frontend.profiles": { items: [{ id: 201, key: "main", name: "Main profile", is_active: true }] },
      "frontend.rules": { items: [{ id: 301, profile_id: 201, priority: 100, host_pattern: "*", path_pattern: "/*", query_conditions: {}, target_release_id: 101, is_active: true }] },
      "frontend.runtime_state": { item: { active_profile_id: 201, fallback_release_id: 101, sticky_enabled: true, sticky_ttl_seconds: 1800, cache_ttl_seconds: 15 } },
      "frontend.allowed_hosts": { items: [{ id: 401, host: "example.vercel.app", is_active: true }] },
      "frontend.audit_log": { items: [{ id: 1, action: "seed", entity_type: "runtime", actor_id: "system", created_at: nowIso() }] },
    },
  };
}

export async function installMockWs(page: Page, opts: MockOptions = {}) {
  const state = buildMockWsState(opts);

  await page.addInitScript((mock: MockWsState) => {
    const channels = mock.channels || {};
    const mode = mock.mode;
    const forceUnauthorized = mock.forceUnauthorized;
    const clients = new Set<any>();

    const resolveRequest = (channel: string, params: Record<string, any>) => {
      if (channel.startsWith("dashboard.source_detail:")) {
        const id = channel.split(":")[1];
        return {
          id: Number(id),
          site_key: "detmir",
          name: "Detmir",
          status: "waiting",
          total_items: 120,
          last_run_new: 7,
          is_active: true,
          url: "https://detmir.ru",
          config: { site_name: "Detmir" },
          history: [],
          aggregate_history: [],
          related_sources: [
            { id: 201, site_key: "detmir", url: "https://detmir.ru/toys", config: { discovery_name: "Toys list" }, category_id: 501, total_items: 10, last_synced_at: "2026-03-10T09:00:00Z", status: "waiting", is_active: true },
          ],
        };
      }
      if (channel.startsWith("dashboard.source_products:")) {
        return { items: [], total: 0 };
      }
      if (channel.startsWith("settings.subscriber:")) {
        return { subscriptions: ["global"], language: "en" };
      }
      if (channel.startsWith("ops.run_detail:")) {
        return {
          item: {
            run_id: Number(channel.split(":")[1]),
            source_id: 10,
            run_status: "running",
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            timeline: [{ status: "queued", at: new Date().toISOString() }, { status: "running", at: new Date().toISOString() }],
            logs: "step 1\nstep 2",
            logs_meta: { chars: 12, lines: 2 },
          },
        };
      }
      if (channel === "catalog.categories") {
        const sources = (channels["dashboard.sources"] || []).filter((s: any) => s.type === "list");
        return { items: sources, total: sources.length };
      }
      if (channel === "catalog.products") return channels["catalog.products"];
      if (channel === "ops.discovery_detail") {
        return { item: { id: params.id || 501, url: "https://detmir.ru/toys", state: "new", products_total: 12, last_run_new: 2, last_run_scraped: 4 } };
      }
      if (channel === "ops.source_items_trend") {
        return { items: [{ date: "2026-03-10", items_new: 12, items_total: 120 }], totals: { items_new: 12, items_total: 120 } };
      }
      if (channel === "llm.logs") {
        const items = Array.isArray(channels["llm.logs"]?.items) ? channels["llm.logs"].items : [];
        const provider = String(params.provider || "").toLowerCase();
        const model = String(params.model || "").toLowerCase();
        const status = String(params.status || "").toLowerCase();
        const filtered = items.filter((it: any) => {
          if (provider && String(it.provider || "").toLowerCase() !== provider) return false;
          if (model && String(it.model || "").toLowerCase() !== model) return false;
          if (status && String(it.status || "").toLowerCase() !== status) return false;
          return true;
        });
        return { items: filtered, total: filtered.length };
      }
      if (channel.startsWith("llm.")) return channels[channel];
      return channels[channel];
    };

    const sendSnapshots = (client: any, list: string[]) => {
      if (mode === "empty") return;
      for (const ch of list) {
        if (mode === "partial" && ch === "dashboard.trends") continue;
        if (mode === "out_of_order" && ch === "dashboard.stats") {
          client._emit({ type: "snapshot", channel: ch, seq: 9, data: channels[ch] });
          client._emit({ type: "snapshot", channel: ch, seq: 7, data: channels[ch] });
          continue;
        }
        if (mode === "duplicate" && ch === "dashboard.stats") {
          client._emit({ type: "snapshot", channel: ch, seq: 7, data: channels[ch] });
          client._emit({ type: "snapshot", channel: ch, seq: 7, data: channels[ch] });
          continue;
        }
        if (channels[ch] !== undefined) {
          client._emit({ type: "snapshot", channel: ch, seq: 1, data: channels[ch] });
        }
      }
    };

    const NativeWebSocket = (window as any).WebSocket;

    class MockWebSocket {
      static CONNECTING = 0;
      static OPEN = 1;
      static CLOSING = 2;
      static CLOSED = 3;
      url: string;
      readyState = MockWebSocket.CONNECTING;
      onopen: ((ev?: any) => void) | null = null;
      onmessage: ((ev: { data: string }) => void) | null = null;
      onclose: ((ev?: any) => void) | null = null;
      constructor(url: string) {
        if (!url.includes("/api/v1/live-analytics/ws")) {
          return new NativeWebSocket(url) as any;
        }
        this.url = url;
        this.readyState = MockWebSocket.OPEN;
        clients.add(this);
        setTimeout(() => this.onopen?.({}), 0);
      }
      _emit(payload: any) {
        const data = JSON.stringify(payload);
        setTimeout(() => this.onmessage?.({ data }), 0);
      }
      send(raw: string) {
        try {
          const msg = JSON.parse(raw);
          if (msg.type === "subscribe") {
            const list = Array.isArray(msg.channels) ? msg.channels : [];
            sendSnapshots(this, list);
          } else if (msg.type === "request") {
            const channel = msg.channel;
            const reqId = msg.req_id;
            const params = msg.params || {};
            if (forceUnauthorized) {
              this._emit({ type: "error", channel, code: "unauthorized", message: "unauthorized", req_id: reqId });
              return;
            }
            const data = resolveRequest(channel, params);
            this._emit({ type: "snapshot", channel, seq: 0, data, req_id: reqId });
          }
        } catch {
          // ignore
        }
      }
      close() {
        this.readyState = MockWebSocket.CLOSED;
        clients.delete(this);
        this.onclose?.({});
      }
      addEventListener(type: string, handler: any) {
        if (type === "open") this.onopen = handler;
        if (type === "message") this.onmessage = handler;
        if (type === "close") this.onclose = handler;
      }
      removeEventListener() {}
    }

    (window as any).WebSocket = MockWebSocket as any;
    (window as any).__adminWsMockUpdate = (channel: string, data: any) => {
      channels[channel] = data;
      clients.forEach((client) => {
        client._emit({ type: "update", channel, seq: Date.now(), data });
      });
    };
  }, state);
}
