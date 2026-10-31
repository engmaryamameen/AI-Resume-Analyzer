import { selectOption } from "./select-option";
import { expect, test } from "@playwright/test";
import path from "node:path";

/**
 * Browser journeys. Each states its expected behaviour and the invariant it protects.
 * They need the full stack running (frontend, API, PostgreSQL and the worker; see the testing
 * documentation under docs/).
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
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/app$/);
}

test("a visitor can try the product with no account, and the result says how it was read", async ({
  page,
}) => {
  // Invariants: the demo needs no credentials or upload; the engine is always stated; listed-only skills are distinguished.
  await page.goto("/demo");
  await selectOption(page.getByLabel("Sample résumé"), {
    label: "Avery Example – Backend Engineer",
  });
  await selectOption(page.getByLabel("Target role"), { index: 1 });
  await page.getByRole("button", { name: "Analyze these documents" }).click();
  await page.getByRole("tab", { name: "Evidence", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Requirement by requirement" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "How this was read", level: 2 })).toBeVisible();
  await expect(
    page.locator(".report-disclosure > summary").getByText("Rule-based reading", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Backed up").first()).toBeVisible();
  await expect(page.getByText("Only mentioned").first()).toBeVisible();
});

test("the demo shows no score, meter or grade", async ({ page }) => {
  await page.goto("/demo");
  await selectOption(page.getByLabel("Sample résumé"), { index: 1 });
  await selectOption(page.getByLabel("Target role"), { index: 1 });
  await page.getByRole("button", { name: "Analyze these documents" }).click();
  await page.getByRole("tab", { name: "Document insights" }).click();
  await expect(page.getByRole("heading", { name: /Four readings/ })).toBeVisible();
  await expect(page.locator('[role="meter"]')).toHaveCount(0);
  await expect(page.getByText(/Looks strong|Needs work/)).toHaveCount(0);
});

test("signed-out visitors are sent to sign in", async ({ page }) => {
  await page.goto("/app/resumes");
  await expect(page).toHaveURL(/\/login/);
});

test("register, upload, review the reading, analyze, edit from a suggestion, compare, export, delete", async ({
  page,
}) => {
  // Invariants: extraction is reviewable before use; analyses reference exact versions; edits make new versions; deletion is complete.
  await signUp(page);

  await page.goto("/app/resumes");
  await page.getByLabel("Choose a file").setInputFiles(sample("synthetic-resume.docx"));
  await expect(page.getByText("Ready", { exact: true })).toBeVisible({ timeout: 30_000 });
  await page.getByRole("link", { name: /synthetic-resume/ }).click();
  await expect(page.getByRole("heading", { name: "Contact details" })).toBeVisible();

  await page.goto("/app/jobs");
  await page
    .getByLabel("Job description")
    .fill(
      "Requirements:\n- Experience with Python and Django\n- Hands-on Kubernetes experience\n- 3+ years of experience",
    );
  await page.getByRole("button", { name: "Find the requirements" }).click();
  await expect(page.getByLabel("Requirement").first()).toBeVisible();

  await page.getByRole("link", { name: "Analyze a résumé" }).click();
  await selectOption(page.getByLabel("Résumé", { exact: true }), { index: 1 });
  await selectOption(page.getByLabel("Job description", { exact: true }), { index: 1 });
  await page.getByRole("button", { name: "Start analysis" }).click();
  await page.getByRole("tab", { name: "Evidence", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Requirement by requirement" })).toBeVisible({
    timeout: 45_000,
  });
  await expect(
    page
      .locator(".report-disclosure > summary")
      .getByText(process.env.E2E_SEMANTIC ? "Local models" : "Rule-based reading", { exact: true }),
  ).toBeVisible();
  const firstAnalysis = page.url();

  // Kubernetes is only listed in the fixture, so there is a suggestion to show it in use.
  await page.getByRole("link", { name: "Suggestions" }).click();
  await expect(
    page.getByText(/A template for you to fill in with true details/).first(),
  ).toBeVisible();
  await page
    .getByLabel("Your line")
    .first()
    .fill("Ran Kubernetes clusters for the catalogue services");
  await expect(page.getByText("What would change")).toBeVisible();
  await page.getByRole("button", { name: "Save this line" }).first().click();
  await expect(page.getByText(/Saved as version 2/)).toBeVisible();
  await page.getByRole("button", { name: "Run the analysis again on the new version" }).click();
  await page.getByRole("tab", { name: "Evidence", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Requirement by requirement" })).toBeVisible({
    timeout: 45_000,
  });

  await page.goto(firstAnalysis);
  await expect(page.getByText("This analysis is out of date")).toBeVisible();
  await expect(page.getByText(/The résumé has been edited since this analysis/)).toBeVisible();

  await page.goto("/app/analyses");
  const boxes = page.getByRole("checkbox");
  await boxes.nth(0).check();
  await boxes.nth(1).check();
  await page.getByRole("button", { name: "Compare the two" }).click();
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

test("a wrong password when deleting the account keeps you signed in and says why", async ({
  page,
}) => {
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
  await page.getByLabel("Choose a file").setInputFiles({
    name: "broken.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.4\nnot a pdf"),
  });
  await expect(page.getByText(/couldn't open this PDF/i)).toBeVisible({ timeout: 45_000 });
  page.once("dialog", (d) => d.accept());
  await page.getByRole("button", { name: /Delete broken/ }).click();
  await expect(page.getByText("No résumés yet")).toBeVisible();
});

test("reading method is explained in settings without a missing-model warning", async ({
  page,
}) => {
  await signUp(page);
  await expect(page.getByRole("heading", { name: "Inference engine status" })).toHaveCount(0);
  await page.goto("/app/settings");
  await expect(page.getByRole("heading", { name: "Reading method" })).toBeVisible();
  await expect(
    page.getByText(process.env.E2E_SEMANTIC ? "Local semantic models" : "Local rules", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.getByText("Models not available")).toHaveCount(0);
});

test("core pages are operable by keyboard alone", async ({ page }) => {
  await page.goto("/demo");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to content" })).toBeFocused();
  await page.keyboard.press("Enter");
  await page.getByLabel("Sample résumé").focus();
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("Enter");
  await page.getByLabel("Target role").focus();
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: "Analyze these documents" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "How this was read", level: 2 })).toBeVisible();
});

test("review history recovers after a brief service interruption", async ({ page }) => {
  await signUp(page);
  let calls = 0;
  await page.route("**/api/v1/analyses?*", async (route) => {
    calls += 1;
    if (calls === 1) await route.fulfill({ status: 503, body: "temporarily unavailable" });
    else await route.continue();
  });
  await page.goto("/app/analyses");
  await expect(page.getByRole("heading", { name: "Review history" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Nothing here yet" })).toBeVisible();
  expect(calls).toBeGreaterThanOrEqual(2);
  await expect(page.getByText("That didn't work")).toHaveCount(0);
});
