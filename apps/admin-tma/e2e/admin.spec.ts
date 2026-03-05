import { test, expect } from "@playwright/test";

async function mockApi(page: any) {
  await page.route("**/api/v1/**", async (route: any) => {
    const req = route.request();
    const url = new URL(req.url());
    const path = url.pathname;
    const method = req.method();

    // Default responses needed for initial render.
    if (method === "GET" && path.endsWith("/internal/stats")) {
      return route.fulfill({ json: { scraped_24h: 0, quiz_completion_rate: 0 } });
    }
    if (method === "GET" && path.endsWith("/internal/health")) {
      return route.fulfill({
        json: {
          api: { status: "Healthy", latency: "10ms" },
          database: { status: "Connected", engine: "PostgreSQL" },
          redis: { status: "Healthy", memory_usage: "10MB" },
          rabbitmq: { status: "Healthy" },
        },
      });
    }
    if (method === "GET" && path.endsWith("/internal/monitoring")) {
      return route.fulfill({ json: [{ id: 10, site_key: "detmir", status: "idle", total_items: 12 }] });
    }
    if (method === "GET" && path.endsWith("/internal/workers")) {
      return route.fulfill({ json: [{ hostname: "w1", cpu_usage_pct: 1, ram_usage_pct: 2, concurrent_tasks: 0 }] });
    }
    if (method === "GET" && path.endsWith("/internal/queues/stats")) {
      return route.fulfill({ json: { messages_total: 0, messages_ready: 0, messages_unacknowledged: 0 } });
    }
    if (method === "GET" && path.endsWith("/analytics/trends")) {
      return route.fulfill({ json: { dates: [], dau_trend: [], quiz_starts: [], last_updated: "now" } });
    }
    if (method === "GET" && path.endsWith("/internal/subscribers/1")) {
      return route.fulfill({ json: { subscriptions: [] } });
    }
    if (method === "GET" && path.endsWith("/internal/ops/runtime-settings")) {
      return route.fulfill({
        json: {
          item: {
            settings_version: 1,
            ops_client_intervals: {},
            bounds: { ops_client_intervals: { min: 1000, max: 600000 } },
          },
        },
      });
    }
    if ((method === "PATCH" || method === "PUT") && path.endsWith("/internal/ops/runtime-settings")) {
      return route.fulfill({ json: { status: "ok" } });
    }
    if (method === "GET" && path.endsWith("/internal/merchants")) {
      return route.fulfill({ json: { items: [], total: 0 } });
    }
    if (method === "GET" && path.endsWith("/internal/products")) {
      return route.fulfill({ json: { items: [], total: 0 } });
    }
    if (method === "GET" && path.endsWith("/internal/logs/services")) {
      return route.fulfill({ json: { items: ["api"] } });
    }
    if (method === "GET" && path.endsWith("/internal/logs/query")) {
      return route.fulfill({
        json: { items: [{ ts: "2026-03-04T00:00:00Z", ts_ns: 1, service: "api", line: "hello world" }] },
      });
    }

    // Frontend routing panel (minimal)
    if (method === "GET" && path.endsWith("/internal/frontend/apps")) return route.fulfill({ json: { items: [] } });
    if (method === "GET" && path.endsWith("/internal/frontend/releases")) return route.fulfill({ json: { items: [] } });
    if (method === "GET" && path.endsWith("/internal/frontend/profiles")) return route.fulfill({ json: { items: [] } });
    if (method === "GET" && path.endsWith("/internal/frontend/rules")) return route.fulfill({ json: { items: [] } });
    if (method === "GET" && path.endsWith("/internal/frontend/runtime-state")) return route.fulfill({ json: { item: {} } });
    if (method === "GET" && path.endsWith("/internal/frontend/allowed-hosts")) return route.fulfill({ json: { items: [] } });
    if (method === "GET" && path.endsWith("/internal/frontend/audit-log")) return route.fulfill({ json: { items: [] } });
    if (method === "POST" && path.endsWith("/internal/frontend/publish")) return route.fulfill({ json: { status: "ok" } });
    if (method === "POST" && path.endsWith("/internal/frontend/rollback")) return route.fulfill({ json: { status: "ok" } });

    // Intelligence
    if (method === "GET" && path.endsWith("/internal/analytics/intelligence")) {
      return route.fulfill({
        json: { metrics: { total_cost: 0, total_tokens: 0, total_requests: 0 }, providers: [], latency_heatmap: [] },
      });
    }

    return route.fulfill({ json: {} });
  });
}

test("app boot + navigation across tabs", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");

  await expect(page.getByTestId("nav-dashboard")).toBeVisible();

  await page.getByTestId("nav-logs").click();
  await expect(page.getByRole("heading", { name: "Logs" })).toBeVisible();

  await page.getByTestId("nav-settings").click();
  await expect(page.getByText("Restore defaults")).toBeVisible();

  await page.getByTestId("nav-frontend").click();
  await expect(page.getByRole("heading", { name: "Apps" })).toBeVisible();
});

test("logs smoke: apply filter and load history", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");

  await page.getByTestId("nav-logs").click();
  await page.getByPlaceholder("Server filter (LogQL contains)...").fill("error");
  await page.getByRole("button", { name: "Apply" }).click();

  await expect(page.getByText("hello world")).toBeVisible();
});

test("settings critical: restore runtime defaults", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");

  await page.getByTestId("nav-settings").click();
  await page.getByRole("button", { name: "Restore defaults" }).click();

  // UI stays stable (no crash) after action.
  await expect(page.getByText("Restore defaults")).toBeVisible();
});
