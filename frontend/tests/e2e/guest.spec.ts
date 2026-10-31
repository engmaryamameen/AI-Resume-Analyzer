import { expect, test } from "@playwright/test";
import path from "node:path";

// Run against a fresh disposable application database. The network allowance intentionally survives
// report deletion, browser contexts and API process restarts; tests cannot silently reset it.
test("one home-page guest analysis works without an account and deletion preserves the 24-hour gate", async ({
  page,
  browser,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/#analyze");
  await page
    .getByLabel("Your résumé file")
    .setInputFiles(path.join(__dirname, "fixtures/synthetic-resume.docx"));
  await page.getByRole("button", { name: "Continue to target role" }).click();
  await page
    .getByLabel("Target job description")
    .fill(
      "Requirements:\n- Experience with Python and Django\n- Hands-on Kubernetes experience\n- 3+ years of experience",
    );
  await page.getByRole("button", { name: "Back to your résumé", exact: true }).click();
  await expect(page.getByText("synthetic-resume.docx", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Continue to target role" }).click();
  await expect(page.getByLabel("Target job description")).toHaveValue(/Hands-on Kubernetes/);
  await page.getByRole("button", { name: "Analyze my résumé for free" }).click();
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
