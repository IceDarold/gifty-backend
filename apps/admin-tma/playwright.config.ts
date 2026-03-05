import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: "http://127.0.0.1:3001",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  webServer: {
    cwd: __dirname,
    command:
      "NEXT_PUBLIC_TEST_MODE=1 NEXT_PUBLIC_DISABLE_SSE=1 NEXT_PUBLIC_TEST_USER_JSON='{ \"id\": 1, \"role\": \"superadmin\", \"permissions\": [\"*\"] }' NEXT_DISABLE_TURBOPACK=1 npx next dev --port 3001 --hostname 127.0.0.1",
    url: "http://127.0.0.1:3001",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
