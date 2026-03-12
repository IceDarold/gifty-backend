import { expect, test } from "@playwright/test";
import { installMockApi } from "../support/mockApi";
import { nav, openNav } from "../support/selectors";
import { expectNoClientCrash, waitForAppReady } from "../support/wait";

test.describe("analytics logs and health", () => {
  test("logs filters and severity classification", async ({ page }) => {
    await installMockApi(page);
    await waitForAppReady(page);

    await openNav(page, nav.logs);
    await expect(page.getByTestId("logs-view")).toBeVisible();

    await page.getByTestId("logs-filter-input").fill("error: failed");
    await page.getByTestId("logs-filter-apply").click();

    await expect(page.getByText("filtered error: failed")).toBeVisible();
    await expect(page.getByTestId("logs-line-0")).toHaveAttribute("data-level", "error");

    await expectNoClientCrash(page);
  });

  test("health status renders normal state", async ({ page }) => {
    await installMockApi(page);
    await waitForAppReady(page);

    await openNav(page, nav.health);
    await expect(page.getByTestId("health-view")).toBeVisible();
    await expect(page.getByTestId("health-api")).toContainText("Healthy");
    await expect(page.getByTestId("health-api")).toContainText("111ms");
    await expect(page.getByTestId("health-db")).toContainText("Connected");
    await expect(page.getByTestId("health-redis")).toContainText("Healthy");

    await expectNoClientCrash(page);
  });

  test("health status renders degraded state", async ({ page }) => {
    await installMockApi(page, { healthMode: "degraded" });
    await waitForAppReady(page);

    await openNav(page, nav.health);
    await expect(page.getByTestId("health-view")).toBeVisible();
    await expect(page.getByTestId("health-api")).toContainText("Degraded");
    await expect(page.getByTestId("health-db")).toContainText("Degraded");
    await expect(page.getByTestId("health-redis")).toContainText("Degraded");

    await expectNoClientCrash(page);
  });
});
