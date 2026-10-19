import { test, expect } from "@playwright/test";
import { FIXTURE_PATHS } from "./helpers";

test.describe("Resume Upload & Repository Management Journeys", () => {
  test("rejects invalid non-PDF and empty files with clear diagnostic errors", async ({ page }) => {
    await page.goto("/resumes");
    await expect(page.getByRole("heading", { name: "Resume Library", level: 2 })).toBeVisible();

    // 1. Attempt uploading invalid .txt file
    const fileInput = page.locator("#resume-file-input");
    await fileInput.setInputFiles(FIXTURE_PATHS.invalidExtension);

    await expect(
      page.getByText("Only PDF documents (.pdf) are supported.")
    ).toBeVisible();

    // 2. Attempt uploading empty 0-byte file
    await fileInput.setInputFiles(FIXTURE_PATHS.emptyPdf);
    await expect(page.getByText("The selected file is empty (0 bytes).")).toBeVisible();
  });

  test("successfully processes valid PDF resume, displays extracted skills, and allows permanent deletion", async ({
    page,
  }) => {
    await page.goto("/resumes");
    await expect(page.getByRole("heading", { name: "Resume Library", level: 2 })).toBeVisible();

    // 1. Select valid PDF resume fixture
    const fileInput = page.locator("#resume-file-input");
    await fileInput.setInputFiles(FIXTURE_PATHS.validResume);

    // Selected file preview should be visible
    await expect(page.locator("p").filter({ hasText: "sample_resume.pdf" }).first()).toBeVisible();

    // Click "Upload & Process"
    await page.getByRole("button", { name: "Upload & Process" }).click();

    // Expect success message
    await expect(
      page.getByText(/Successfully processed and indexed 'sample_resume.pdf'/i)
    ).toBeVisible({ timeout: 30000 });

    // 2. Resume Card should be present in library list
    const resumeCard = page.locator("div.grid").filter({ hasText: "sample_resume.pdf" });
    await expect(resumeCard).toBeVisible();

    // Should display extracted skills badges
    await expect(page.getByText("Docker").first()).toBeVisible();
    await expect(page.getByText("FastAPI").first()).toBeVisible();

    // 3. Open Details Modal
    await page.getByRole("button", { name: "Details" }).first().click();
    const detailsDialog = page.getByRole("dialog", { name: "Resume Details" });
    await expect(detailsDialog).toBeVisible();
    await expect(detailsDialog.getByText("Extracted Taxonomy Skills")).toBeVisible();
    await expect(detailsDialog.getByText("Python")).toBeVisible();

    // Close Details Modal
    await detailsDialog.getByRole("button", { name: "Close", exact: true }).click();
    await expect(detailsDialog).not.toBeVisible();

    // 4. Test Permanent Deletion (GDPR Cleanup)
    await page.getByRole("button", { name: "Delete" }).first().click();
    const deleteModal = page.getByRole("dialog", { name: "Confirm Resume Deletion" });
    await expect(deleteModal).toBeVisible();
    await expect(
      deleteModal.getByText("In strict compliance with GDPR Right to Be Forgotten")
    ).toBeVisible();

    await deleteModal.getByRole("button", { name: "Permanently Delete" }).click();

    // Verify deletion feedback and empty repository state
    await expect(
      page.getByText(/permanently deleted/i)
    ).toBeVisible({ timeout: 15000 });
  });
});
