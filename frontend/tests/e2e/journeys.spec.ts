import { expect, test } from "@playwright/test";
import path from "node:path";

/**
 * Browser journeys. Each states its expected behaviour and the invariant it protects.
 * They need the full stack running (frontend, API, PostgreSQL and the worker; see the testing
 * documentation under docs/) and have not been run.
 *
 * Run `python frontend/tests/e2e/fixtures/make_fixture.py` once to create the DOCX fixture.
 * With no approved models installed, analyses use the rule-based reading, which these journeys expect.
 */

const sample = (name: string) => path.join(__dirname, "fixtures", name);
const unique = () => `e2e-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
const PASSWORD = "a long and unusual passphrase";

async function signUp(page: import("@playwright/test").Page) {
  await page.goto("/register");
  await page.getByLabel("Email").fill(unique());
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/app$/);
}

test("a visitor can try the product with no account, and the result says how it was read", async ({ page }) => {
  // Invariants: the demo needs no credentials or upload; the engine is always stated; listed-only skills are distinguished.
  await page.goto("/demo");
  await page.getByLabel("Résumé").selectOption({ label: "Avery Example – Backend Engineer" });
  await page.getByLabel("Job description").selectOption({ index: 1 });
  await page.getByRole("button", { name: "Analyse" }).click();
  await expect(page.getByRole("heading", { name: "Requirement by requirement" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "How this was read" })).toBeVisible();
  await expect(page.getByText("Rule-based reading")).toBeVisible();
  await expect(page.getByText("Backed up").first()).toBeVisible();
  await expect(page.getByText("Only mentioned").first()).toBeVisible();
});

test("the demo shows no score, meter or grade", async ({ page }) => {
  await page.goto("/demo");
  await page.getByLabel("Résumé").selectOption({ index: 1 });
  await page.getByLabel("Job description").selectOption({ index: 1 });
  await page.getByRole("button", { name: "Analyse" }).click();
  await expect(page.getByRole("heading", { name: /Four readings/ })).toBeVisible();
  await expect(page.locator('[role="meter"]')).toHaveCount(0);
  await expect(page.getByText(/Looks strong|Needs work/)).toHaveCount(0);
});

test("signed-out visitors are sent to sign in", async ({ page }) => {
  await page.goto("/app/resumes");
  await expect(page).toHaveURL(/\/login/);
});

test("register, upload, review the reading, analyse, edit from a suggestion, compare, export, delete", async ({ page }) => {
  // Invariants: extraction is reviewable before use; analyses reference exact versions; edits make new versions; deletion is complete.
  await signUp(page);

  await page.goto("/app/resumes");
  await page.getByLabel("Choose a file").setInputFiles(sample("synthetic-resume.docx"));
  await expect(page.getByText("Ready", { exact: true })).toBeVisible({ timeout: 30_000 });
  await page.getByRole("link", { name: /synthetic-resume/ }).click();
  await expect(page.getByRole("heading", { name: "Contact details" })).toBeVisible();

  await page.goto("/app/jobs");
  await page.getByLabel("Job description").fill("Requirements:\n- Experience with Python and Django\n- Hands-on Kubernetes experience\n- 3+ years of experience");
  await page.getByRole("button", { name: "Find the requirements" }).click();
  await expect(page.getByLabel("Requirement").first()).toBeVisible();

  await page.getByRole("link", { name: "Analyse a résumé" }).click();
  await page.getByLabel("Résumé").selectOption({ index: 1 });
  await page.getByLabel("Job description").selectOption({ index: 1 });
  await page.getByRole("button", { name: "Start analysis" }).click();
  await expect(page.getByRole("heading", { name: "Requirement by requirement" })).toBeVisible({ timeout: 45_000 });
  await expect(page.getByText("Rule-based reading")).toBeVisible();
  const firstAnalysis = page.url();

  // Kubernetes is only listed in the fixture, so there is a suggestion to show it in use.
  await page.getByRole("link", { name: "Suggestions" }).click();
  await expect(page.getByText(/A template for you to fill in with true details/).first()).toBeVisible();
  await page.getByLabel("Your line").first().fill("Ran Kubernetes clusters for the catalogue services");
  await expect(page.getByText("What would change")).toBeVisible();
  await page.getByRole("button", { name: "Save this line" }).first().click();
  await expect(page.getByText(/Saved as version 2/)).toBeVisible();
  await page.getByRole("button", { name: "Run the analysis again on the new version" }).click();
  await expect(page.getByRole("heading", { name: "Requirement by requirement" })).toBeVisible({ timeout: 45_000 });

  await page.goto(firstAnalysis);
  await expect(page.getByText("This analysis is out of date")).toBeVisible();
  await expect(page.getByText(/The résumé has been edited since this analysis/)).toBeVisible();

  await page.goto("/app/analyses");
  const boxes = page.getByRole("checkbox");
  await boxes.nth(0).check();
  await boxes.nth(1).check();
  await page.getByRole("link", { name: "Compare the two" }).click();
  await expect(page.getByRole("heading", { name: "Requirements" })).toBeVisible();

  await page.goto(firstAnalysis);
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: /Download CSV/ }).click();
  expect((await download).suggestedFilename()).toMatch(/\.csv$/);

  await page.goto("/app/settings");
  await page.getByLabel("Your password").fill(PASSWORD);
  page.once("dialog", (d) => d.accept());
  await page.getByRole("button", { name: "Delete my account and data" }).click();
  await expect(page).toHaveURL("/");
  await page.goto("/app");
  await expect(page).toHaveURL(/\/login/);
});

test("a wrong password when deleting the account keeps you signed in and says why", async ({ page }) => {
  // Invariant: a 403 on re-authentication is not treated as a lost session.
  await signUp(page);
  await page.goto("/app/settings");
  await page.getByLabel("Your password").fill("not the right password");
  page.once("dialog", (d) => d.accept());
  await page.getByRole("button", { name: "Delete my account and data" }).click();
  await expect(page.getByText("That password isn't right.")).toBeVisible();
  await expect(page).toHaveURL(/\/app\/settings/);
});

test("an unreadable upload explains what to do next, and can be deleted", async ({ page }) => {
  await signUp(page);
  await page.goto("/app/resumes");
  await page.getByLabel("Choose a file").setInputFiles({ name: "broken.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4\nnot a pdf") });
  await expect(page.getByText(/couldn't open this PDF/i)).toBeVisible({ timeout: 45_000 });
  page.once("dialog", (d) => d.accept());
  await page.getByRole("button", { name: /Delete broken/ }).click();
  await expect(page.getByText("No résumés yet")).toBeVisible();
});

test("the model status is visible in the workspace", async ({ page }) => {
  await signUp(page);
  await expect(page.getByRole("heading", { name: "Analysis models on this server" })).toBeVisible();
});

test("core pages are operable by keyboard alone", async ({ page }) => {
  await page.goto("/demo");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to content" })).toBeFocused();
  await page.keyboard.press("Enter");
  await page.getByLabel("Résumé").focus();
  await page.keyboard.press("ArrowDown");
  await page.getByLabel("Job description").focus();
  await page.keyboard.press("ArrowDown");
  await page.getByRole("button", { name: "Analyse" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "How this was read" })).toBeVisible();
});
