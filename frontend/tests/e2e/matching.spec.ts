import { test, expect } from "@playwright/test";
import { FIXTURE_PATHS } from "./helpers";

test.describe("Real-Time Explainable Match Evaluation Journeys", () => {
  test("complete end-to-end matching workflow: resume ingestion, job analysis, multi-dimensional evaluation, history inspection, and safe cleanup", async ({
    page,
  }) => {
    // 1. Upload valid candidate PDF resume (tenant authenticated via storageState)
    await page.goto("/resumes");
    const fileInput = page.locator("#resume-file-input");
    await fileInput.setInputFiles(FIXTURE_PATHS.validResume);
    await page.getByRole("button", { name: "Upload & Process" }).click();
    await expect(
      page.getByText(/Successfully processed and indexed 'sample_resume.pdf'/i)
    ).toBeVisible({ timeout: 30000 });

    // 3. Ingest and analyze job description
    await page.goto("/jobs");
    const presetCard = page.getByRole("button", { name: /Select preset: Senior Backend Engineer/i });
    await presetCard.click();
    await page.getByRole("button", { name: "Extract Requirements" }).click();
    await expect(
      page.getByText(/Successfully parsed requirements for 'Senior Backend Engineer'/i)
    ).toBeVisible({ timeout: 30000 });

    // 4. Navigate to Matches page
    await page.goto("/matches");
    await expect(
      page.getByRole("heading", { name: "Real-Time Matching & Explainable Diagnostics" })
    ).toBeVisible();

    // Verify option selectors loaded candidate resume and job
    const resumeSelect = page.locator("#resume-select");
    const jobSelect = page.locator("#job-select");
    await expect(resumeSelect).toBeVisible();
    await expect(jobSelect).toBeVisible();

    // 5. Execute Match Evaluation
    const runMatchBtn = page.getByRole("button", { name: "Run Match Evaluation" });
    await expect(runMatchBtn).toBeEnabled();
    await runMatchBtn.click();

    // 6. Assert Overall Match Results Card
    await expect(page.getByText("Evaluation Results & Explainable Attribution")).toBeVisible({
      timeout: 30000,
    });
    await expect(page.getByText("Overall Match Score")).toBeVisible();
    await expect(page.getByText("/ 100").first()).toBeVisible();

    // Assert Component Contributions (all 4 canonical weights)
    await expect(page.getByText(/Semantic Similarity \(50% weight\)/i)).toBeVisible();
    await expect(page.getByText(/Skills Alignment \(30% weight\)/i)).toBeVisible();
    await expect(page.getByText(/Experience Duration \(10% weight\)/i)).toBeVisible();
    await expect(page.getByText(/Education Level \(10% weight\)/i)).toBeVisible();

    // Assert Skills Alignment Breakdown
    await expect(page.getByText("Skills Alignment Breakdown")).toBeVisible();
    await expect(page.getByText(/Matched Required Skills/i)).toBeVisible();

    // 7. Verify History Table Entry
    await expect(page.getByRole("heading", { name: "Historical Match Evaluations" })).toBeVisible();
    const historyTable = page.locator("table");
    await expect(historyTable).toBeVisible();
    await expect(historyTable.getByRole("button", { name: "Inspect" }).first()).toBeVisible();

    // 8. Inspect Match Modal
    await historyTable.getByRole("button", { name: "Inspect" }).first().click();
    await expect(page.getByRole("heading", { name: "Match Diagnostic Breakdown" })).toBeVisible();
    await page.getByRole("button", { name: "Close Breakdown" }).click();
    await expect(page.getByRole("heading", { name: "Match Diagnostic Breakdown" })).not.toBeVisible();

    // 9. Cleanup: Delete match record
    await historyTable.getByRole("button", { name: "Delete" }).first().click();
    await expect(page.getByRole("heading", { name: "Delete Match Evaluation" })).toBeVisible();
    await page.getByRole("button", { name: "Permanently Delete" }).click();

    await expect(
      page.getByText("Match evaluation record permanently deleted.")
    ).toBeVisible({ timeout: 15000 });
  });
});
