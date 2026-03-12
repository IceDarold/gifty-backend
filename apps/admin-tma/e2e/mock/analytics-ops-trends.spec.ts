import { expect, test } from "@playwright/test";
import { installMockApi } from "../support/mockApi";
import { nav, openNav } from "../support/selectors";
import { expectNoClientCrash, waitForAppReady } from "../support/wait";

test.describe("analytics ops trends and tabs", () => {
  test.beforeEach(async ({ page }) => {
    await installMockApi(page, { opsMode: "full" });
    await waitForAppReady(page);
  });

  test("stats and trends render", async ({ page }) => {
    await openNav(page, nav.ops);

    await expect(page.getByTestId("ops-view")).toBeVisible();
    await expect(page.getByTestId("ops-task-states")).toBeVisible();
    await expect(page.getByTestId("ops-items-trend-chart")).toBeVisible();
    await expect(page.getByTestId("ops-tasks-trend-chart")).toBeVisible();

    await expectNoClientCrash(page);
  });

  test("parsers, categories, queue, workers, scheduler tabs", async ({ page }) => {
    await openNav(page, nav.ops);

    await page.getByTestId("ops-tab-parsers").click();
    await expect(page.getByTestId("ops-parsers-search")).toBeVisible();
    await expect(page.getByTestId("ops-parser-detmir")).toBeVisible();
    await page.getByRole("button", { name: "Run discovery" }).first().click();

    await page.getByTestId("ops-tab-categories").click();
    await expect(page.getByTestId("ops-categories")).toBeVisible();
    await expect(page.getByTestId("categories-table")).toBeVisible();
    await expect(page.getByTestId("category-row-12")).toBeVisible();

    await page.getByTestId("ops-tab-queue").click();
    await expect(page.getByTestId("ops-queue-lane-queued")).toBeVisible();
    await expect(page.getByTestId("ops-queue-item-queued-9002")).toBeVisible();

    await page.getByTestId("ops-tab-workers").click();
    await expect(page.getByTestId("ops-workers")).toBeVisible();
    await expect(page.getByTestId("ops-worker-w1:1")).toBeVisible();

    await page.getByTestId("ops-tab-scheduler").click();
    await expect(page.getByTestId("ops-scheduler")).toBeVisible();
    await page.getByTestId("ops-scheduler-toggle").click();

    await expectNoClientCrash(page);
  });
});
