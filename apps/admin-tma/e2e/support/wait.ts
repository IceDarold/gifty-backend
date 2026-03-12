import { expect, type Page } from "@playwright/test";

export async function waitForAppReady(page: Page) {
  await page.goto("/");
  await expect(page.getByTestId("nav-ops")).toBeVisible();
  await expect(page.getByText("Operations Center")).toBeVisible();
  // Ensure no fatal Next.js runtime overlay text is shown.
  await expect(page.getByText("Application error: a client-side exception has occurred")).toHaveCount(0);
}

export async function expectNoClientCrash(page: Page) {
  await expect(page.getByText("Application error: a client-side exception has occurred")).toHaveCount(0);
  await expect(page.getByText("Runtime TypeError")).toHaveCount(0);
  // Avoid screenshots capturing untranslated loading placeholder.
  await expect(page.getByText("common.loading")).toHaveCount(0);
}
