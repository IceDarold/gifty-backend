import { expect, test } from "@playwright/test";
import { installMockApi } from "../support/mockApi";
import { nav, openNav } from "../support/selectors";
import { expectNoClientCrash, waitForAppReady } from "../support/wait";

test.describe("admin mock: top-level navigation", () => {
  test.beforeEach(async ({ page }) => {
    await installMockApi(page);
    await waitForAppReady(page);
  });

  test("navigates through all top-level sections and renders key blocks", async ({ page }) => {
    await openNav(page, nav.dashboard);
    await expect(page.getByText("Live System")).toBeVisible();

    await openNav(page, nav.catalog);
    await expect(page.getByRole("heading", { name: "Global Catalog" })).toBeVisible();

    await openNav(page, nav.intelligence);
    await expect(page.getByRole("heading", { name: "AI Intelligence" })).toBeVisible();

    await openNav(page, nav.llmLogs);
    await expect(page.getByRole("heading", { name: "LLM Logs" })).toBeVisible();

    await openNav(page, nav.health);
    await expect(page.getByRole("heading", { name: "System Health" })).toBeVisible();

    await openNav(page, nav.logs);
    await expect(page.getByRole("heading", { name: "Logs" })).toBeVisible();

    await openNav(page, nav.frontend);
    await expect(page.getByRole("heading", { name: "Apps" })).toBeVisible();

    await openNav(page, nav.settings);
    await expect(page.getByText("System / Performance")).toBeVisible();

    await openNav(page, nav.ops);
    await expect(page.getByText("Operations Center")).toBeVisible();

    await expectNoClientCrash(page);
  });

  test("logs page supports filter/apply/reconnect path", async ({ page }) => {
    await openNav(page, nav.logs);
    await page.getByTestId("logs-filter-input").fill("error");
    await page.getByTestId("logs-filter-apply").click();
    await expect(page.getByText("filtered error")).toBeVisible();

    await page.getByRole("button", { name: "Pause" }).click();
    await expect(page.getByRole("button", { name: "Resume" })).toBeVisible();
    await page.getByRole("button", { name: "Resume" }).click();

    await expectNoClientCrash(page);
  });
});
