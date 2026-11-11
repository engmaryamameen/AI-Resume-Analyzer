import { expect, test } from "@playwright/test";
import path from "node:path";
import { readFile } from "node:fs/promises";

// Run against a fresh disposable application database. The network allowance intentionally survives
// report deletion, browser contexts and API process restarts; tests cannot silently reset it.
test("a lost guest response recovers the same private review and deletion preserves the 24-hour gate", async ({
  page,
  browser,
}) => {
  // This destructive quota test must start with a fresh disposable E2E database.
  // A previous run intentionally leaves the network blocked even after deleting its report.
  const preflight = await page.request.get("/api/v1/guest");
  expect(preflight.ok(), `Guest status request returned ${preflight.status()}`).toBe(true);
  const guest = (await preflight.json()) as { available: boolean; status?: string };
  expect(
    guest.available,
    `Guest E2E network allowance is already consumed (status: ${guest.status ?? "unknown"}). ` +
      "Use a fresh disposable Compose project/database for each guest E2E run.",
  ).toBe(true);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/#analyze");
  await expect(page.getByLabel("Your résumé file")).toBeAttached();
  await page
    .getByLabel("Your résumé file")
    .setInputFiles(path.join(__dirname, "fixtures/synthetic-resume.docx"));
  await page.getByRole("button", { name: "Add a target role (optional)" }).click();
  await page
    .getByLabel("Target job description")
    .fill(
      "Requirements:\n- Experience with Python and Django\n- Hands-on Kubernetes experience\n- 3+ years of experience",
    );
  await page.getByRole("button", { name: "Back to your résumé", exact: true }).click();
  await expect(page.getByText("synthetic-resume.docx", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Add a target role (optional)" }).click();
  await expect(page.getByLabel("Target job description")).toHaveValue(/Hands-on Kubernetes/);
  const keys: string[] = [];
  page.on("request", (request) => {
    if (request.url().endsWith("/api/v1/guest/analyze"))
      keys.push(request.headers()["idempotency-key"] ?? "");
  });
  await page.route(
    "**/api/v1/guest/analyze",
    async (route) => {
      // The real API commits before we lose the response. No successful outcome is mocked.
      // Chromium interception omits file bytes from postData; forward the actual fixture.
      const accepted = await page.request.post(route.request().url(), {
        headers: {
          Origin: new URL(page.url()).origin,
          "Idempotency-Key": route.request().headers()["idempotency-key"]!,
        },
        multipart: {
          file: {
            name: "synthetic-resume.docx",
            mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            buffer: await readFile(path.join(__dirname, "fixtures/synthetic-resume.docx")),
          },
          job_text: await page.getByLabel("Target job description").inputValue(),
        },
      });
      expect(accepted.status(), await accepted.text()).toBe(202);
      await page.context().clearCookies({ name: "mn_guest" });
      await route.abort("failed");
    },
    { times: 1 },
  );
  await page.getByRole("button", { name: "Analyze my résumé for free" }).click();
  const recover = page.getByRole("button", { name: "Recover my existing review" });
  await expect(recover).toBeEnabled();
  await expect(page.getByLabel("Target job description")).toBeDisabled();
  const withoutCookie = await page.request.get("/api/v1/guest");
  expect(await withoutCookie.json()).toMatchObject({
    available: false,
    status: "idle",
    report: null,
  });
  await recover.click();
  await expect.poll(() => keys.length).toBe(2);
  expect(keys[0]).not.toBe("");
  expect(keys[1]).toBe(keys[0]);
  await expect(page.getByRole("heading", { name: "Your résumé review" })).toBeVisible({
    timeout: 45000,
  });
  await expect(page.getByRole("heading", { name: "Your résumé review" })).toBeFocused();
  await expect(page.locator("h1")).toHaveCount(1);
  await expect(
    page
      .getByText(process.env.E2E_SEMANTIC ? "Local models" : "Local rule-based reader", {
        exact: true,
      })
      .first(),
  ).toBeVisible();
  await page.screenshot({
    path: test.info().outputPath("guest-review.png"),
    fullPage: true,
    animations: "disabled",
  });
  await page.screenshot({
    path: test.info().outputPath("guest-review.jpg"),
    type: "jpeg",
    quality: 80,
    animations: "disabled",
  });
  expect((await page.request.get("/api/v1/auth/me")).status()).toBe(401);
  page.once("dialog", (d) => d.accept());
  await page.getByRole("button", { name: "Delete guest report" }).click();
  await expect(page.getByRole("heading", { name: "You’ve used your free review." })).toBeVisible();
  const fresh = await browser.newContext();
  const visitor = await fresh.newPage();
  await visitor.goto(new URL("/#analyze", page.url()).href);
  await expect(
    visitor.getByRole("heading", { name: "You’ve used your free review." }),
  ).toBeVisible();
  await expect(visitor.getByText(/Next free analysis/)).toBeVisible();
  await expect(visitor.getByRole("link", { name: "Create a free account" })).toBeVisible();
  await fresh.close();
});
