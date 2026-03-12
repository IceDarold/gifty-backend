import type { Page } from "@playwright/test";

export const nav = {
  ops: "nav-ops",
  dashboard: "nav-dashboard",
  catalog: "nav-catalog",
  intelligence: "nav-intelligence",
  llmLogs: "nav-llm_logs",
  health: "nav-health",
  logs: "nav-logs",
  frontend: "nav-frontend",
  settings: "nav-settings",
} as const;

export async function openNav(page: Page, id: string) {
  await page.getByTestId(id).click();
}
