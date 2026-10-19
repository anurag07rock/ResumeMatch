import { test as setup, expect } from "@playwright/test";
import path from "path";
import fs from "fs";
import { TEST_PASSWORD } from "./helpers";

const authFile = path.resolve(__dirname, ".auth/user.json");
const testEmail = "e2e_suite_candidate@test.local";

setup("authenticate test tenant session", async ({ page }) => {
  // Ensure storage state directory exists
  const dir = path.dirname(authFile);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }

  // Attempt login
  await page.goto("/login");
  await page.getByLabel("Email address").fill(testEmail);
  await page.getByLabel("Password").fill(TEST_PASSWORD);
  await page.getByRole("button", { name: "Sign In" }).click();

  let loggedIn = false;
  try {
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 8000 });
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
    loggedIn = true;
  } catch {
    // If sign-in didn't redirect, check if account needs registration
  }

  if (!loggedIn) {
    await page.goto("/register");
    await page.getByLabel("Full name (Optional)").fill("Playwright E2E Candidate");
    await page.getByLabel("Email address").fill(testEmail);
    await page.getByLabel("Password").fill(TEST_PASSWORD);
    await page.getByRole("button", { name: "Create Account" }).click();
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  }

  // Persist the authenticated cookie session for test reuse
  await page.context().storageState({ path: authFile });
});
