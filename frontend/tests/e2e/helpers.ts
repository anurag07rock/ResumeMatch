import { Page, expect } from "@playwright/test";
import path from "path";

/**
 * Common test credentials and fixtures for Playwright E2E browser journeys.
 * Uses disposable test accounts with zero persistence of sensitive data.
 */
export const TEST_PASSWORD = "TestPass123!@#";

export function generateTestEmail(prefix = "e2e_user"): string {
  const timestamp = Date.now();
  const random = Math.floor(Math.random() * 10000);
  return `${prefix}_${timestamp}_${random}@test.local`;
}

export const FIXTURE_PATHS = {
  validResume: path.resolve(__dirname, "../fixtures/sample_resume.pdf"),
  invalidExtension: path.resolve(__dirname, "../fixtures/invalid_extension.txt"),
  fakePdf: path.resolve(__dirname, "../fixtures/fake_pdf.pdf"),
  emptyPdf: path.resolve(__dirname, "../fixtures/empty.pdf"),
};

/**
 * Ensures an authenticated session is active by attempting login first,
 * falling back to registration if the test account has not yet been provisioned.
 * This prevents triggering authentication endpoint rate limits during test runs.
 */
export async function ensureAuthenticated(
  page: Page,
  email = "e2e_suite_candidate@test.local",
  password = TEST_PASSWORD
): Promise<void> {
  // If already authenticated on a portal page
  if (
    page.url().includes("/dashboard") ||
    page.url().includes("/resumes") ||
    page.url().includes("/jobs") ||
    page.url().includes("/matches")
  ) {
    const logoutBtn = page.getByRole("button", { name: "Log Out" });
    if (await logoutBtn.isVisible().catch(() => false)) {
      return;
    }
  }

  await page.goto("/login");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign In" }).click();

  try {
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 8000 });
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
    return;
  } catch {
    // If sign-in didn't redirect, check if user needs to be registered
  }

  // User not yet registered, proceed to registration
  await page.goto("/register");
  await page.getByLabel("Full name (Optional)").fill("Playwright E2E Candidate");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Create Account" }).click();
  await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
}

/**
 * Registers a new disposable user and awaits landing on the dashboard.
 */
export async function registerTestUser(
  page: Page,
  email?: string,
  fullName = "Playwright E2E Candidate"
): Promise<{ email: string; password: string }> {
  const userEmail = email || generateTestEmail();

  await page.goto("/register");
  await expect(page.getByRole("heading", { name: "Create your account" })).toBeVisible();

  // Fill registration form
  await page.getByLabel("Full name (Optional)").fill(fullName);
  await page.getByLabel("Email address").fill(userEmail);
  await page.getByLabel("Password").fill(TEST_PASSWORD);

  // Submit
  await page.getByRole("button", { name: "Create Account" }).click();

  // Should navigate to dashboard
  await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();

  return { email: userEmail, password: TEST_PASSWORD };
}

/**
 * Logs in with specified credentials and verifies redirection to dashboard.
 */
export async function loginUser(
  page: Page,
  email: string,
  password = TEST_PASSWORD
): Promise<void> {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Sign in to your account" })).toBeVisible();

  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign In" }).click();

  await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
}

/**
 * Logs out via the portal header.
 */
export async function logoutUser(page: Page): Promise<void> {
  const logoutBtn = page.getByRole("button", { name: "Log Out" });
  await expect(logoutBtn).toBeVisible();
  await logoutBtn.click();
  // Portal layout redirects unauthenticated user to /login?from=...
  await expect(page).toHaveURL(/\/login/, { timeout: 15000 });
  await expect(page.getByRole("heading", { name: "Sign in to your account" })).toBeVisible();
}
