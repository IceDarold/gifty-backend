import { defineConfig, devices } from "@playwright/test";

const appBaseUrl = process.env.E2E_APP_BASE_URL || "http://127.0.0.1:3001";
const apiBaseUrl = process.env.E2E_API_BASE_URL || "http://127.0.0.1:8000";
const liveBaseUrl = process.env.E2E_LIVE_ANALYTICS_BASE_URL || "http://127.0.0.1:8095";
const internalToken = process.env.E2E_INTERNAL_API_TOKEN || process.env.NEXT_PUBLIC_API_INTERNAL_TOKEN || "your_internal_api_token";
const liveToken = process.env.E2E_LIVE_ANALYTICS_WS_TOKEN || process.env.NEXT_PUBLIC_LIVE_ANALYTICS_WS_TOKEN || "dev-live-analytics-token";

const testUserJson = '{ "id": 1, "role": "superadmin", "permissions": ["*"] }';
const webServerCommand = [
  "NEXT_PUBLIC_TEST_MODE=1",
  "NEXT_PUBLIC_DISABLE_SSE=1",
  `NEXT_PUBLIC_TEST_USER_JSON='${testUserJson}'`,
  `NEXT_PUBLIC_API_BASE_URL='${apiBaseUrl}'`,
  `NEXT_PUBLIC_API_INTERNAL_TOKEN='${internalToken}'`,
  `NEXT_PUBLIC_LIVE_ANALYTICS_BASE_URL='${liveBaseUrl}'`,
  `NEXT_PUBLIC_LIVE_ANALYTICS_WS_TOKEN='${liveToken}'`,
  "NEXT_DISABLE_TURBOPACK=1",
  "npx next dev --port 3001 --hostname 127.0.0.1",
].join(" ");

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: appBaseUrl,
    trace: "on",
    screenshot: "on",
    video: "retain-on-failure",
  },
  webServer: {
    cwd: __dirname,
    command: webServerCommand,
    url: appBaseUrl,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
  projects: [
    {
      name: "chromium-mock",
      testMatch: ["e2e/mock/**/*.spec.ts"],
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "chromium-integration",
      testMatch: ["e2e/integration/**/*.spec.ts"],
      retries: process.env.CI ? 2 : 0,
      timeout: 90_000,
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
