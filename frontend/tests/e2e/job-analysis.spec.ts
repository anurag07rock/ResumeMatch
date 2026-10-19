import { test, expect } from "@playwright/test";

test.describe("Job Description Analysis Journeys", () => {
  test("validates required job form inputs", async ({ page }) => {
    await page.goto("/jobs");
    await expect(page.getByRole("heading", { name: "Job Requirements Analysis", level: 2 })).toBeVisible();

    // Click Extract Requirements with empty fields
    await page.getByRole("button", { name: "Extract Requirements" }).click();
    await expect(page.getByText("Job title is required.")).toBeVisible();
    await expect(page.getByText("Job description text is required.")).toBeVisible();
  });

  test("selects sample preset, extracts requirements, inspects details, and deletes job", async ({
    page,
  }) => {
    await page.goto("/jobs");
    await expect(page.getByRole("heading", { name: "Job Requirements Analysis", level: 2 })).toBeVisible();

    // 1. Click sample preset card "Senior Backend Engineer"
    const presetCard = page.getByRole("button", { name: /Select preset: Senior Backend Engineer/i });
    await expect(presetCard).toBeVisible();
    await presetCard.click();

    // Verify fields populated
    const titleInput = page.getByLabel("Job Title *");
    await expect(titleInput).toHaveValue("Senior Backend Engineer");

    // 2. Submit extraction
    await page.getByRole("button", { name: "Extract Requirements" }).click();

    // Success alert should appear
    await expect(
      page.getByText(/Successfully parsed requirements for 'Senior Backend Engineer'/i)
    ).toBeVisible({ timeout: 30000 });

    // Extracted requirements preview should display parsed badges
    await expect(page.getByText("Parsed Just Now")).toBeVisible();
    await expect(page.getByText("Experience Minimum")).toBeVisible();

    // 3. Analyzed Job should appear in the library list
    const jobRow = page.locator("div.grid").filter({ hasText: "Senior Backend Engineer" });
    await expect(jobRow.first()).toBeVisible();

    // 4. Inspect Job Details modal
    await page.getByRole("button", { name: "Details" }).first().click();
    const detailsDialog = page.getByRole("dialog", { name: "Job Details" });
    await expect(detailsDialog).toBeVisible();
    await expect(detailsDialog.getByText("Required Technical Skills")).toBeVisible();

    // Close modal
    await detailsDialog.getByRole("button", { name: "Close", exact: true }).click();
    await expect(detailsDialog).not.toBeVisible();

    // 5. Delete Job Record
    await page.getByRole("button", { name: "Delete" }).first().click();
    const deleteModal = page.getByRole("dialog", { name: "Confirm Job Deletion" });
    await expect(deleteModal).toBeVisible();

    await deleteModal.getByRole("button", { name: "Permanently Delete" }).click();
    await expect(
      page.getByText(/Job 'Senior Backend Engineer' permanently deleted/i)
    ).toBeVisible({ timeout: 15000 });
  });
});
