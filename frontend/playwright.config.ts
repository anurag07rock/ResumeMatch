import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright E2E Browser Testing Configuration for ResumeMatch
 *
 * Configured for deterministic execution against the local or CI Next.js
 * frontend and FastAPI backend stack.
 */
export default defineConfig({
  testDir: "./tests/e2e",
  /* Maximum time one test can run for. Extended for CPU sentence-transformer embeddings. */
  timeout: 60 * 1000,
  expect: {
    /* Timeout for individual assertions */
    timeout: 15 * 1000,
  },
  /* Run tests sequentially to ensure clean tenant isolation */
  fullyParallel: false,
  /* Fail the build on CI if you accidentally left test.only in the source code. */
  forbidOnly: Boolean(process.env.CI),
  /* Retry on CI only */
  retries: process.env.CI ? 1 : 0,
  /* Sequential worker count avoids database collision on test accounts */
  workers: 1,
  /* Reporter to use */
  reporter: [
    ["list"],
    ["html", { outputFolder: "playwright-report", open: "never" }],
  ],
  use: {
    /* Base URL to use in actions like `await page.goto('/')`. */
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000",
    /* Collect trace when retrying the failed test. */
    trace: "on-first-retry",
    /* Capture screenshot only when test fails */
    screenshot: "only-on-failure",
    /* Record video only on failure */
    video: "retain-on-failure",
    /* Headless mode */
    headless: true,
  },

  /* Configure projects */
  projects: [
    {
      name: "setup",
      testMatch: /.*\.setup\.ts/,
    },
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        storageState: "tests/e2e/.auth/user.json",
      },
      dependencies: ["setup"],
    },
  ],

  /* Optional web server setup if not already running */
  webServer: process.env.PLAYWRIGHT_SKIP_WEBSERVER
    ? undefined
    : {
        command: "npm run start",
        url: "http://localhost:3000",
        reuseExistingServer: true,
        timeout: 120 * 1000,
      },
});
