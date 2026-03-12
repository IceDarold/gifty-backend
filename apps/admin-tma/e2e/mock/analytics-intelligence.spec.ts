import { expect, test } from "@playwright/test";
import { installMockApi } from "../support/mockApi";
import { nav, openNav } from "../support/selectors";
import { expectNoClientCrash, waitForAppReady } from "../support/wait";

test.describe("analytics intelligence", () => {
  test("metrics correctness and provider distribution", async ({ page }) => {
    await installMockApi(page, { intelligenceMode: "full" });
    await waitForAppReady(page);

    await openNav(page, nav.intelligence);

    await expect(page.getByTestId("intelligence")).toBeVisible();
    await expect(page.getByTestId("intelligence-total-cost")).toHaveText("$1.70");
    await expect(page.getByTestId("intelligence-total-tokens")).toContainText("12.3k");
    await expect(page.getByTestId("intelligence-total-requests")).toContainText("88");
    await expect(page.getByTestId("intelligence-provider-anthropic")).toContainText("40 calls");
    await expect(page.getByText("0.9s")).toBeVisible();

    await expectNoClientCrash(page);
  });

  test("partial payload does not crash UI", async ({ page }) => {
    await installMockApi(page, { intelligenceMode: "partial" });
    await waitForAppReady(page);

    await openNav(page, nav.intelligence);
    await expect(page.getByTestId("intelligence-total-cost")).toHaveText("$1.70");
    await expect(page.getByTestId("intelligence-total-tokens")).toContainText("0.0k");
    await expectNoClientCrash(page);
  });

  test("error payload renders fallback", async ({ page }) => {
    await installMockApi(page, { intelligenceMode: "error" });
    await waitForAppReady(page);

    await openNav(page, nav.intelligence);
    await expect(page.getByTestId("intelligence-error")).toBeVisible();
    await expectNoClientCrash(page);
  });
});
