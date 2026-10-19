import { test, expect } from "@playwright/test";

test.describe("Landing Page & Navigation Guards", () => {
  // Navigation and access guard tests run unauthenticated
  test.use({ storageState: { cookies: [], origins: [] } });

  test("landing page renders brand, hero, and navigation links correctly", async ({ page }) => {
    await page.goto("/");

    // Verify Title & Meta
    await expect(page).toHaveTitle(/ResumeMatch — Explainable AI/);

    // Verify Brand Logo & Headline
    await expect(page.getByText("ResumeMatch").first()).toBeVisible();
    await expect(
      page.getByRole("heading", { name: /Explainable AI-Powered/i })
    ).toBeVisible();

    // Verify Core Guarantees are visible
    await expect(page.getByText("Zero Hallucination")).toBeVisible();
    await expect(page.getByText("100% Deterministic Reproducibility")).toBeVisible();
    await expect(page.getByText("GDPR Instant Purge")).toBeVisible();

    // Verify Navigation Links in Landing Header
    const nav = page.getByRole("navigation");
    await expect(nav.getByRole("link", { name: "Dashboard" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Resumes" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Jobs" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Matches" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Launch App" })).toBeVisible();

    // Verify Dimensions Section
    await expect(page.getByText("Semantic Similarity")).toBeVisible();
    await expect(page.getByText("Skills Alignment")).toBeVisible();
  });

  test("unauthenticated visitors are redirected to login when accessing portal routes", async ({
    page,
  }) => {
    const protectedRoutes = ["/dashboard", "/resumes", "/jobs", "/matches", "/settings"];

    for (const route of protectedRoutes) {
      await page.goto(route);
      await page.waitForURL((url) => url.pathname === "/login", { timeout: 10000 });
      expect(page.url()).toContain(`/login?from=${encodeURIComponent(route)}`);
      await expect(page.getByRole("heading", { name: "Sign in to your account" })).toBeVisible();
    }
  });
});
