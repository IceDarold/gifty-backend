import { expect, test } from "@playwright/test";
import { installMockApi } from "../support/mockApi";
import { nav, openNav } from "../support/selectors";
import { expectNoClientCrash, waitForAppReady } from "../support/wait";

test.describe("analytics dashboard correctness", () => {
  test.beforeEach(async ({ page }) => {
    await installMockApi(page);
    await waitForAppReady(page);
  });

  test("kpi cards and trends render expected values", async ({ page }) => {
    await openNav(page, nav.dashboard);

    await expect(page.getByTestId("stat-active-spiders-value")).toHaveText("3");
    await expect(page.getByTestId("stat-items-scraped-value")).toHaveText(/12,345/);
    await expect(page.getByTestId("stat-discovery-rate-value")).toHaveText("42%");
    await expect(page.getByTestId("stat-latency-value")).toHaveText("111ms");

    await expect(page.getByTestId("usage-chart")).toBeVisible();
    await expect(page.getByTestId("usage-chart-empty")).toHaveCount(0);
    await expect(page.getByTestId("infra-panel")).toBeVisible();

    await expectNoClientCrash(page);
  });

  test("spider detail tabs and categories pagination", async ({ page }) => {
    await openNav(page, nav.dashboard);

    await page.getByTestId("spider-open-10").click();
    await expect(page.getByTestId("spider-detail")).toBeVisible();

    await page.getByTestId("spider-detail-tab-overview").click();
    await expect(page.getByTestId("spider-detail-overview")).toBeVisible();
    await expect(page.getByTestId("spider-detail-stats")).toBeVisible();

    await page.getByTestId("spider-detail-tab-categories").click();
    await expect(page.getByTestId("spider-detail-categories")).toBeVisible();
    await page.getByTestId("spider-detail-categories-search").fill("toy");
    await expect(page.getByTestId("spider-detail-categories-table")).toBeVisible();
    await expect(page.getByTestId("spider-detail-categories-prev")).toBeVisible();
    await expect(page.getByTestId("spider-detail-categories-next")).toBeVisible();

    await expectNoClientCrash(page);
  });
});
