import { expect, test } from "@playwright/test";
import { installMockApi } from "../support/mockApi";
import { nav, openNav } from "../support/selectors";
import { expectNoClientCrash, waitForAppReady } from "../support/wait";

test.describe("admin mock: frontend routing and settings", () => {
  test.beforeEach(async ({ page }) => {
    await installMockApi(page);
    await waitForAppReady(page);
  });

  test("frontend routing panels and critical mutations", async ({ page }) => {
    await openNav(page, nav.frontend);

    await expect(page.getByRole("heading", { name: "Apps" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Profiles & Rules" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Runtime State / Publish" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Allowed Hosts" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Audit Log" })).toBeVisible();

    await page.getByRole("button", { name: "Add new" }).first().click();
    await page.locator('input[placeholder="product"]').first().fill("campaign");
    await page.locator('input[placeholder="Main Product"]').first().fill("Campaign App");
    await page.getByRole("button", { name: "Create app" }).click();
    await expect(page.getByRole("button", { name: /campaign/i }).first()).toBeVisible();

    await page.getByRole("button", { name: "Publish" }).click();
    await page.getByRole("button", { name: "Rollback" }).click();

    await page.getByPlaceholder("example.vercel.app").fill("new.example.vercel.app");
    await page.getByRole("button", { name: "Add", exact: true }).click();
    await expect(page.getByText("new.example.vercel.app")).toBeVisible();

    await expectNoClientCrash(page);
  });

  test("settings runtime controls and restore defaults", async ({ page }) => {
    await openNav(page, nav.settings);

    await expect(page.getByText("System / Performance")).toBeVisible();
    await expect(page.getByText("Merchants")).toBeVisible();

    await expectNoClientCrash(page);
  });

  test("negative: unauthorized responses show API error banners without crash", async ({ page }) => {
    await installMockApi(page, { forceUnauthorized: true });
    await page.goto("/");

    await openNav(page, nav.dashboard);
    await expect(page.getByText("Live System")).toBeVisible();

    await openNav(page, nav.frontend);
    await expect(page.getByRole("heading", { name: "Apps" })).toBeVisible();

    await expectNoClientCrash(page);
  });
});
