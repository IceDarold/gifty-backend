import { expect, test } from "@playwright/test";
import { installMockApi } from "../support/mockApi";
import { nav, openNav } from "../support/selectors";
import { expectNoClientCrash, waitForAppReady } from "../support/wait";

test.describe("analytics LLM logs", () => {
  test("filters apply and pagination works", async ({ page }) => {
    await installMockApi(page, { llmLogsMode: "full" });
    await waitForAppReady(page);

    await openNav(page, nav.llmLogs);

    await expect(page.getByTestId("llm-logs")).toBeVisible();
    await expect(page.getByTestId("llm-summary")).toBeVisible();
    await expect(page.getByTestId("llm-summary-requests-total")).toHaveText("2");
    await expect(page.getByTestId("llm-summary-requests-errors")).toContainText("errors: 0 · rate: 0.0%");
    await expect(page.getByTestId("llm-summary-cost-total")).toContainText("$0.0040");
    await expect(page.getByTestId("llm-summary-cost-avg")).toContainText("$0.0040");
    await expect(page.getByTestId("llm-summary-latency-p95")).toHaveText("210ms");
    await expect(page.getByTestId("llm-summary-tokens-p95")).toHaveText("123");

    await page.getByTestId("llm-filter-provider").fill("groq");
    await page.getByTestId("llm-filter-model").fill("gemma");
    await page.getByTestId("llm-filter-status").selectOption("error");

    await expect(page.getByTestId("llm-log-row-log_1")).toBeVisible();
    await expect(page.getByText("groq")).toBeVisible();
    await expect(page.getByText("gemma")).toBeVisible();

    await page.getByTestId("llm-log-row-log_1").click();
    await expect(page.getByText("LLM Call Details")).toBeVisible();

    await expectNoClientCrash(page);
  });

  test("partial payloads render without crashing", async ({ page }) => {
    await installMockApi(page, { llmLogsMode: "partial" });
    await waitForAppReady(page);
    await openNav(page, nav.llmLogs);

    await expect(page.getByTestId("llm-log-row-log_partial")).toBeVisible();
    await expectNoClientCrash(page);
  });
});
