import { expect, test } from "@playwright/test";
import { installMockApi } from "../support/mockApi";
import { nav, openNav } from "../support/selectors";
import { expectNoClientCrash, waitForAppReady } from "../support/wait";

test.describe("analytics negative and slow paths", () => {
  test("unauthorized responses do not crash analytics views", async ({ page }) => {
    await installMockApi(page, { forceUnauthorized: true });
    await waitForAppReady(page);

    await openNav(page, nav.dashboard);
    await expect(page.getByText("Live System")).toBeVisible();

    await openNav(page, nav.intelligence);
    await expect(page.getByTestId("intelligence")).toBeVisible();

    await openNav(page, nav.llmLogs);
    await expect(page.getByTestId("llm-logs")).toBeVisible();

    await openNav(page, nav.health);
    await expect(page.getByTestId("health-view")).toBeVisible();

    await openNav(page, nav.logs);
    await expect(page.getByTestId("logs-view")).toBeVisible();

    await openNav(page, nav.ops);
    await expect(page.getByTestId("ops-view")).toBeVisible();

    await expectNoClientCrash(page);
  });

  test("slow responses keep UI stable", async ({ page }) => {
    await installMockApi(page, { delayMs: 1500 });
    await waitForAppReady(page);

    await openNav(page, nav.intelligence);
    await expect(page.getByTestId("intelligence")).toBeVisible();

    await openNav(page, nav.llmLogs);
    await expect(page.getByTestId("llm-logs")).toBeVisible();
    await expect(page.getByTestId("llm-summary")).toBeVisible();

    await expectNoClientCrash(page);
  });
});
