import { test, expect } from "@playwright/test";
import { generateTestEmail, TEST_PASSWORD, loginUser, logoutUser } from "./helpers";

test.describe("Authentication & Session Management Journeys", () => {
  // Auth form tests run without existing session
  test.use({ storageState: { cookies: [], origins: [] } });

  test("login form validates required fields and email formatting", async ({ page }) => {
    await page.goto("/login");

    // Attempt submission with empty fields
    await page.getByRole("button", { name: "Sign In" }).click();
    await expect(page.getByText("Email address is required.")).toBeVisible();
    await expect(page.getByText("Password is required.")).toBeVisible();

    // Fill invalid email format
    await page.getByLabel("Email address").fill("invalid-email-format");
    await page.getByLabel("Password").fill("anyPassword1!");
    await page.getByRole("button", { name: "Sign In" }).click();

    await expect(
      page.getByText("Please enter a valid email address (e.g. name@example.com).")
    ).toBeVisible();
  });

  test("login displays error alert when invalid credentials are provided", async ({ page }) => {
    await page.goto("/login");

    await page.getByLabel("Email address").fill("nonexistent_user@test.local");
    await page.getByLabel("Password").fill("WrongPassword123!");
    await page.getByRole("button", { name: "Sign In" }).click();

    await expect(page.getByText("Sign In Failed")).toBeVisible();
    await expect(page.getByText(/Invalid email or password/i)).toBeVisible();
  });

  test("registration validates password complexity checklist", async ({ page }) => {
    await page.goto("/register");

    await page.getByLabel("Email address").fill("newcandidate@test.local");

    // Enter a weak password (no uppercase, no special, no digit)
    const passwordInput = page.getByLabel("Password");
    await passwordInput.fill("simple");

    // Password requirements checklist indicators
    await expect(page.getByText("Password Requirements:")).toBeVisible();
    await expect(page.getByText("≥ 8 characters")).toBeVisible();
    await expect(page.getByText("1 uppercase letter")).toBeVisible();
    await expect(page.getByText("1 numeric digit")).toBeVisible();
    await expect(page.getByText("1 special symbol")).toBeVisible();

    // Click submit, expect error
    await page.getByRole("button", { name: "Create Account" }).click();
    await expect(
      page.getByText(/Password must be at least 8 characters long|complexity criteria/i)
    ).toBeVisible();
  });

  test("full authentication lifecycle: registration, session persistence, logout, and login", async ({
    page,
  }) => {
    const testEmail = generateTestEmail("auth_flow");
    const testName = "Jane E2E Candidate";

    // 1. Register new user
    await page.goto("/register");
    await page.getByLabel("Full name (Optional)").fill(testName);
    await page.getByLabel("Email address").fill(testEmail);
    await page.getByLabel("Password").fill(TEST_PASSWORD);

    await page.getByRole("button", { name: "Create Account" }).click();

    // 2. Redirect to dashboard
    await page.waitForURL("**/dashboard", { timeout: 15000 });
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();

    // 3. Verify user name in header
    await expect(page.locator("header").getByText(testName)).toBeVisible();

    // 4. Log out
    await logoutUser(page);

    // 5. Verify protected route is now inaccessible
    await page.goto("/dashboard");
    await page.waitForURL((url) => url.pathname === "/login", { timeout: 10000 });

    // 6. Log back in with registered credentials
    await loginUser(page, testEmail, TEST_PASSWORD);
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  });
});
