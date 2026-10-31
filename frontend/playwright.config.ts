import { defineConfig } from "@playwright/test";

// Full-stack journeys against a running API, PostgreSQL, worker and production frontend.
export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 60_000,
  retries: 0,
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
    channel: process.env.E2E_CHANNEL,
  },
  reporter: [["list"]],
});
