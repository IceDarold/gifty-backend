import { expect, test } from "@playwright/test";
import { nav, openNav } from "../support/selectors";
import { expectNoClientCrash } from "../support/wait";
import { getIntegrationEnv, precheckIntegration, publishEventsAndWaitForUI } from "../support/integration";

const env = getIntegrationEnv();
let skipReason = "";

test.describe("live analytics pipeline", () => {
  test.beforeAll(async ({ request }) => {
    const status = await precheckIntegration(request, env);
    if (!status.ok) {
      skipReason = status.reason;
      return;
    }
  });

  test("nats -> snapshot/ws -> ui no crash", async ({ page, request }) => {
    test.skip(!!skipReason, skipReason);
    test.skip(!env.natsPublishEnabled, "NATS publish disabled");

    await page.goto("/");
    await openNav(page, nav.dashboard);
    await expect(page.getByTestId("stats-grid")).toBeVisible();

    const published = await publishEventsAndWaitForUI(request, env, { expectedDelta: 1, timeoutMs: 15000, attempts: 3 });
    expect(published.ok, published.details).toBeTruthy();

    const wsBase = env.liveBaseUrl.replace(/^http/, "ws");
    const wsMessage = await page.evaluate(
      ({ wsBaseUrl, token }) =>
        new Promise<string>((resolve, reject) => {
          const ws = new WebSocket(`${wsBaseUrl}/api/v1/live-analytics/ws?access_token=${encodeURIComponent(token)}`);
          const timer = setTimeout(() => {
            ws.close();
            reject(new Error("ws timeout"));
          }, 8000);

          ws.onopen = () => {
            ws.send(JSON.stringify({ type: "subscribe", channels: ["global.kpi"] }));
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

    expect(wsMessage.length).toBeGreaterThan(0);

    await expectNoClientCrash(page);
  });
});
