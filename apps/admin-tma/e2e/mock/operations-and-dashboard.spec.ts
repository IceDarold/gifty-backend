import { expect, test } from "@playwright/test";
import { installMockApi } from "../support/mockApi";
import { nav, openNav } from "../support/selectors";
import { expectNoClientCrash, waitForAppReady } from "../support/wait";

test.describe("admin mock: dashboard, spider detail, operations", () => {
  test.beforeEach(async ({ page }) => {
    await installMockApi(page);
    await waitForAppReady(page);
  });

  test("dashboard cards and spider detail modal", async ({ page }) => {
    await openNav(page, nav.dashboard);
    await expect(page.getByText("Live System")).toBeVisible();
    await expect(page.getByRole("button", { name: "Run All" })).toBeVisible();
    await expect(page.getByTestId("spider-open-10")).toBeVisible();

    await page.getByTestId("spider-open-10").click();
    await expect(page.getByRole("button", { name: /Run detmir/i })).toBeVisible();

    await expectNoClientCrash(page);
  });

  test("catalog search, pagination and refresh path", async ({ page }) => {
    await openNav(page, nav.catalog);
    await expect(page.getByRole("heading", { name: "Global Catalog" })).toBeVisible();

    await page.getByPlaceholder("Search by title...").fill("perfume");
    await expect(page.getByText("Perfume Gift")).toBeVisible();

    await expect(page.getByRole("button", { name: /^Prev$/, exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: /^Next$/, exact: true })).toBeVisible();
    await expectNoClientCrash(page);
  });

  test("operations tabs and critical controls", async ({ page }) => {
    await openNav(page, nav.ops);
    await expect(page.getByText("Operations Center")).toBeVisible();

    for (const tab of ["Stats", "Parsers", "Categories", "Queue", "Workers", "Scheduler"]) {
      await page.getByRole("button", { name: tab, exact: true }).first().click();
      await expect(page.getByRole("button", { name: tab, exact: true }).first()).toBeVisible();
    }

    await page.getByRole("button", { name: "Parsers" }).click();
    await page.getByRole("button", { name: "Run discovery" }).first().click();
    await page.getByRole("button", { name: "Open parser card" }).first().click();
    await expect(page.getByRole("button", { name: "Run discovery" }).first()).toBeVisible();

    await page.getByRole("button", { name: "Scheduler" }).click();
    await page.getByRole("button", { name: "Pause scheduler" }).click();

    await expectNoClientCrash(page);
  });
});
