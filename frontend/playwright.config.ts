import { defineConfig } from "@playwright/test";

// E2E specs describe the full stack (frontend + API + PostgreSQL + worker). They are written but
// have not been run; see docs/testing.md for the environment they expect.
export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 60_000,
  retries: 0,
  use: { baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000", trace: "retain-on-failure" },
  reporter: [["list"]],
});
