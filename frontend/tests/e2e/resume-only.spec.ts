import { expect, test } from "@playwright/test";
import path from "node:path";

test("an account can upload, parse and review a résumé without creating a target role", async ({
  page,
}) => {
  await page.goto("/register");
  await page.getByLabel("Email").fill(`resume-only-${Date.now()}@example.test`);
  await page
    .getByLabel("Password", { exact: true })
    .fill("Synthetic resume-only review passphrase");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/app$/);
  await page.goto("/app/resumes");
  await page
    .getByLabel("Choose a file")
    .setInputFiles(path.join(__dirname, "fixtures/synthetic-resume.docx"));
  await expect(page.getByText("Ready", { exact: true })).toBeVisible({ timeout: 30000 });
  await page.getByRole("link", { name: /synthetic-resume/ }).click();
  await page.getByRole("link", { name: "Review this résumé" }).click();
  await expect(page.getByRole("button", { name: "Start analysis" })).toBeEnabled();
  await page.getByRole("button", { name: "Start analysis" }).click();
  await expect(page).toHaveURL(/\/app\/analyses\/[^/]+$/);
  await expect(page.getByRole("tab", { name: "Document insights" })).toBeVisible({
    timeout: 45000,
  });
  await expect(page.getByText("Missing or conflicting", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("tab", { name: "Evidence", exact: true })).toHaveCount(0);
  await page.getByRole("tab", { name: "Document insights" }).click();
  await expect(page.getByRole("heading", { name: "Document checks, at a glance" })).toBeVisible();
});
