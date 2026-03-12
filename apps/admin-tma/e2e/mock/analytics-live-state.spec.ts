import { expect, test } from "@playwright/test";
import { installMockApi } from "../support/mockApi";
import { nav, openNav } from "../support/selectors";
import { expectNoClientCrash, waitForAppReady } from "../support/wait";

const modes = ["normal", "empty", "partial", "out_of_order", "duplicate"] as const;

test.describe("live analytics snapshot modes", () => {
  for (const mode of modes) {
    test(`mode: ${mode}`, async ({ page }) => {
      await installMockApi(page, { liveSnapshotMode: mode });
      await waitForAppReady(page);

      await openNav(page, nav.dashboard);
      await expect(page.getByTestId("stats-grid")).toBeVisible();
      await expect(page.getByTestId("usage-chart")).toBeVisible();
      await expectNoClientCrash(page);
    });
  }
});
