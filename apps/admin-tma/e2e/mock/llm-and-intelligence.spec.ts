import { expect, test } from "@playwright/test";
import { installMockApi } from "../support/mockApi";
import { nav, openNav } from "../support/selectors";
import { expectNoClientCrash, waitForAppReady } from "../support/wait";

test.describe("admin mock: intelligence and llm logs", () => {
  test.beforeEach(async ({ page }) => {
    await installMockApi(page);
    await waitForAppReady(page);
  });

  test("intelligence panel renders metrics", async ({ page }) => {
    await openNav(page, nav.intelligence);

    await expect(page.getByRole("heading", { name: "AI Intelligence" })).toBeVisible();
    await expect(page.getByText("LLM performance, latency and cost tracking")).toBeVisible();
    await expect(page.getByText("$1.70")).toBeVisible();
    await expect(page.getByText("Provider Distribution")).toBeVisible();

    await expectNoClientCrash(page);
  });

  test("llm logs filters and details modal", async ({ page }) => {
    await openNav(page, nav.llmLogs);

    await expect(page.getByRole("heading", { name: "LLM Logs" })).toBeVisible();
    await page.getByPlaceholder("groq / anthropic / gemini...").fill("anthropic");
    await page.getByRole("button", { name: "Refresh" }).click();

    await page.getByRole("button", { name: /anthropic/i }).first().click();
    await expect(page.getByText("LLM Call Details")).toBeVisible();
    await page.keyboard.press("Escape");

    await expectNoClientCrash(page);
  });
});
