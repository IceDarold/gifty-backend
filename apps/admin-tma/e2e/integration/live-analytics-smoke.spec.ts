import { expect, test } from "@playwright/test";
import { nav, openNav } from "../support/selectors";
import { expectNoClientCrash } from "../support/wait";
import { getIntegrationEnv, precheckIntegration, publishNatsEvent } from "../support/integration";

const env = getIntegrationEnv();
let skipReason = "";

test.describe("admin integration smoke", () => {
  test.beforeAll(async ({ request }) => {
    const status = await precheckIntegration(request, env);
    if (!status.ok) {
      skipReason = status.reason;
      return;
    }

    if (env.natsPublishEnabled) {
      const published = publishNatsEvent(env);
      if (!published.ok) {
        skipReason = `nats publish failed: ${published.details}`;
      }
    }
  });

  test("critical navigation on live stack", async ({ page }) => {
    test.skip(!!skipReason, skipReason);

    await page.goto("/");
    await expect(page.getByTestId(nav.ops)).toBeVisible();

    await openNav(page, nav.dashboard);
    await expect(page.getByText("Live System")).toBeVisible();

    await openNav(page, nav.logs);
    await expect(page.getByRole("heading", { name: "Logs" })).toBeVisible();

    await openNav(page, nav.settings);
    await expect(page.getByRole("button", { name: "Restore defaults" })).toBeVisible();

    await expectNoClientCrash(page);
  });

  test("live analytics snapshot and websocket contract", async ({ page, request }) => {
    test.skip(!!skipReason, skipReason);

    const snapshot = await request.get(`${env.liveBaseUrl}/api/v1/live-analytics/snapshot?channels=global.kpi,global.funnel`);
    expect(snapshot.ok()).toBeTruthy();

    const json = (await snapshot.json()) as { items?: Array<{ channel?: string; seq?: number; data?: Record<string, unknown> }> };
    expect(Array.isArray(json.items)).toBeTruthy();

    await page.goto("/");
    await openNav(page, nav.dashboard);

    const wsBase = env.liveBaseUrl.replace(/^http/, "ws");
    const firstMessage = await page.evaluate(
      ({ wsBaseUrl, token }) =>
        new Promise<string>((resolve, reject) => {
          const ws = new WebSocket(`${wsBaseUrl}/api/v1/live-analytics/ws?access_token=${encodeURIComponent(token)}`);
          const timer = setTimeout(() => {
            ws.close();
            reject(new Error("ws timeout"));
          }, 12000);

          ws.onopen = () => {
            ws.send(JSON.stringify({ type: "subscribe", channels: ["global.kpi", "global.funnel"] }));
            ws.send(JSON.stringify({ type: "ping" }));
          };

          ws.onmessage = (event) => {
            clearTimeout(timer);
            ws.close();
            resolve(String(event.data));
          };

          ws.onerror = () => {
            clearTimeout(timer);
            ws.close();
            reject(new Error("ws error"));
          };
        }),
      {
        wsBaseUrl: wsBase,
        token: env.liveWsToken,
      },
    );

    expect(firstMessage.length).toBeGreaterThan(0);
    await expectNoClientCrash(page);
  });
});
