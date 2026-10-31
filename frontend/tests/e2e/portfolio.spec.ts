import { expect, test } from "@playwright/test";
import { selectOption } from "./select-option";

const password = "synthetic portfolio regression passphrase";
async function register(page: import("@playwright/test").Page) {
  await page.goto("/register");
  await page
    .getByLabel("Email")
    .fill(`portfolio-${Date.now()}-${Math.random().toString(36).slice(2, 7)}@example.test`);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Create account", exact: true }).click();
  await expect(page).toHaveURL(/\/app$/);
}
async function removeAccount(page: import("@playwright/test").Page) {
  await page.goto("/app/settings");
  await page.getByLabel("Your password").fill(password);
  page.once("dialog", (d) => d.accept());
  await page.getByRole("button", { name: "Delete my account and data" }).click();
  await expect(page).toHaveURL("/");
}

test("analysis choices paginate without submitting, preserve selection, and bind retry keys to inputs", async ({
  page,
}) => {
  await register(page);
  try {
    const now = "2026-10-31T09:00:00Z";
    const records = Array.from({ length: 21 }, (_, i) => ({
      id: `resume-${i + 1}`,
      title: `Résumé ${i + 1}`,
      created_at: now,
      latest_version: {
        id: `rv-${i + 1}`,
        version_no: 1,
        source: "upload",
        status: "ready",
        error_code: null,
        parseability: null,
        created_at: now,
      },
    }));
    const jobs = [1, 2].map((i) => ({
      id: `role-${i}`,
      title: `Target role ${i}`,
      created_at: now,
      latest_version: { id: `jv-${i}`, version_no: 1, source: "upload", created_at: now },
    }));
    await page.route("**/api/v1/resumes?*", (route) => {
      const offset = Number(new URL(route.request().url()).searchParams.get("offset"));
      return route.fulfill({
        json: { items: records.slice(offset, offset + 20), total: 21, limit: 20, offset },
      });
    });
    await page.route("**/api/v1/job-descriptions?*", (route) =>
      route.fulfill({ json: { items: jobs, total: 2, limit: 20, offset: 0 } }),
    );
    const attempts: {
      key: string | undefined;
      payload: { resume_version_id: string; jd_version_id: string };
    }[] = [];
    await page.route("**/api/v1/analyses", async (route) => {
      if (route.request().method() !== "POST") return route.continue();
      attempts.push({
        key: route.request().headers()["idempotency-key"],
        payload: route.request().postDataJSON(),
      });
      await route.fulfill({
        status: 503,
        json: { code: "service_unavailable", message: "Temporary test interruption" },
      });
    });
    await page.goto("/app/analyses/new");
    const resume = page.getByRole("combobox", { name: "Résumé", exact: true });
    await selectOption(resume, { index: 1 });
    await selectOption(page.getByRole("combobox", { name: "Job description", exact: true }), {
      index: 1,
    });
    await page
      .locator('[aria-label="Résumé choices"]')
      .getByRole("button", { name: "Next", exact: true })
      .click();
    await selectOption(resume, { label: "Résumé 21 (latest version, 1)" });
    expect(attempts).toHaveLength(0);
    await page
      .locator('[aria-label="Résumé choices"]')
      .getByRole("button", { name: "Previous", exact: true })
      .click();
    await expect(resume).toHaveText(/Résumé 21/);
    const job = page.getByRole("combobox", { name: "Job description", exact: true });
    await selectOption(job, { index: 1 });
    const start = page.getByRole("button", { name: "Start analysis", exact: true });
    await start.click();
    await expect(page.getByRole("main").getByRole("alert")).toBeVisible();
    await expect(start).toBeEnabled();
    await start.click();
    await expect.poll(() => attempts.length).toBe(2);
    await expect(start).toBeEnabled();
    expect(attempts[0]!.key).toBeTruthy();
    expect(attempts[1]!.key).toBe(attempts[0]!.key);
    expect(attempts[0]!.payload.resume_version_id).toBe("rv-21");
    await selectOption(job, { index: 2 });
    await start.click();
    await expect.poll(() => attempts.length).toBe(3);
    await expect(start).toBeEnabled();
    expect(attempts[2]!.key).not.toBe(attempts[0]!.key);
    expect(attempts[2]!.payload.jd_version_id).toBe("jv-2");
  } finally {
    await removeAccount(page);
  }
});

test("requirement edits reject invalid experience years and blank requirements before saving", async ({
  page,
}) => {
  await register(page);
  try {
    await page.goto("/app/jobs");
    await page.getByLabel("Role name").fill("Synthetic engineering review");
    await page
      .getByLabel("Job description")
      .fill(
        "Requirements:\n- 5+ years of software engineering experience\n- Experience with Python and PostgreSQL",
      );
    await page.getByRole("button", { name: "Find the requirements" }).click();
    const years = page.getByLabel("Minimum years");
    await expect(years).toBeVisible();
    await years.fill("not a number");
    await page.getByRole("button", { name: "Save changes", exact: true }).click();
    await expect(page.getByRole("main").getByRole("alert")).toContainText("between 0 and 60");
    await years.fill("5");
    await page.getByLabel("Requirement", { exact: true }).first().fill("");
    await page.getByRole("button", { name: "Save changes", exact: true }).click();
    await expect(page.getByRole("main").getByRole("alert")).toContainText("remove the empty row");
  } finally {
    await removeAccount(page);
  }
});

test("a failed sign-out keeps the workspace visible and explains the error", async ({ page }) => {
  await register(page);
  try {
    await page.route("**/api/v1/auth/logout", (route) =>
      route.fulfill({
        status: 503,
        json: {
          error: {
            code: "service_unavailable",
            message: "Temporary test interruption",
            details: {},
          },
        },
      }),
    );
    await page.getByRole("button", { name: "Sign out", exact: true }).click();
    await expect(page.locator("aside").getByRole("alert")).toBeVisible();
    await expect(page).toHaveURL(/\/app$/);
    expect((await page.request.get("/api/v1/auth/me")).status()).toBe(200);
    await expect(page.getByRole("button", { name: "Sign out", exact: true })).toBeEnabled();
  } finally {
    await removeAccount(page);
  }
});
