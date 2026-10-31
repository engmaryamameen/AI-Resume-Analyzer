import { selectOption } from "./select-option";
import { expect, test } from "@playwright/test";
import axe from "axe-core";

for (const width of [320, 390, 1440]) {
  test(`public surfaces are accessible and fit a ${width}px viewport`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    for (const route of ["/", "/demo", "/register", "/login", "/privacy"]) {
      await page.goto(route);
      await page.evaluate(() => document.fonts.ready);
      await expect(page.locator("h1")).toBeVisible();
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
      ).toBe(true);
      await page.addScriptTag({ content: axe.source });
      const violations = await page.evaluate(
        async () =>
          (
            await (window as typeof window & { axe: typeof axe }).axe.run(document, {
              runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21aa"] },
            })
          ).violations,
      );
      expect(violations, `${route} at ${width}px`).toEqual([]);
    }
  });
}

test("a demo reviewer can inspect sources and filter actual findings", async ({ page }) => {
  await page.goto("/demo");
  await selectOption(page.getByLabel("Sample résumé"), { index: 1 });
  await selectOption(page.getByLabel("Target role"), { index: 1 });
  await page.getByRole("button", { name: "Analyze these documents" }).click();
  await page.getByRole("tab", { name: "Evidence", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Requirement by requirement" })).toBeVisible();
  await page.getByText("Inspect the source documents").click();
  await expect(page.getByRole("heading", { name: "Résumé · extracted text" })).toBeVisible();
  await page.getByRole("searchbox").fill("zzzz-unmatched");
  await expect(page.getByText(/No requirements match these filters/)).toBeVisible();
  await page.getByRole("button", { name: "Clear filters" }).click();
  await expect(page.getByRole("heading", { name: "Python", exact: true })).toBeVisible();
});

for (const width of [390, 1440]) {
  test(`workspace surfaces are accessible and fit a ${width}px viewport`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/register");
    await page.getByLabel("Email").fill(`layout-${width}-${Date.now()}@example.test`);
    await page
      .getByLabel("Password", { exact: true })
      .fill("a synthetic layout testing passphrase");
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(page).toHaveURL(/\/app$/);
    for (const route of [
      "/app",
      "/app/resumes",
      "/app/jobs",
      "/app/analyses",
      "/app/analyses/new",
      "/app/analyses/compare",
      "/app/settings",
    ]) {
      await page.goto(route);
      await expect(page.locator("h1")).toBeVisible();
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
        route,
      ).toBe(true);
      await page.addScriptTag({ content: axe.source });
      const violations = await page.evaluate(async () =>
        (
          await (window as typeof window & { axe: typeof axe }).axe.run(document, {
            runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21aa"] },
          })
        ).violations.map((v) => ({
          id: v.id,
          nodes: v.nodes.map((n) => ({ target: n.target, reason: n.failureSummary })),
        })),
      );
      expect(violations, `${route} at ${width}px`).toEqual([]);
    }
  });
}

test("dropdown options are styled, keyboard accessible and dismiss without committing", async ({
  page,
}) => {
  await page.goto("/demo");
  const control = page.getByRole("combobox", { name: /Sample résumé/ });
  await control.click();
  await expect(page.getByRole("listbox")).toBeVisible();
  await expect(page.getByRole("option").first()).toContainText("Avery");
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("Escape");
  await expect(control).toHaveText(/Select a résumé/);
  await control.press("ArrowDown");
  await control.press("Enter");
  await expect(control).toHaveText(/Avery/);
  await control.click();
  await page.addScriptTag({ content: axe.source });
  const issues = await page.evaluate(async () =>
    (
      await (window as typeof window & { axe: typeof axe }).axe.run(document, {
        runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21aa"] },
      })
    ).violations.map((v) => ({ id: v.id, nodes: v.nodes.map((n) => n.target) })),
  );
  expect(issues).toEqual([]);
});

test("long reports begin compact and reveal one requirement's evidence", async ({ page }) => {
  await page.goto("/demo");
  await selectOption(page.getByLabel("Sample résumé"), { index: 1 });
  await selectOption(page.getByLabel("Target role"), { index: 1 });
  await page.getByRole("button", { name: "Analyze these documents" }).click();
  await expect(page.getByRole("heading", { name: "Start with these improvements" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Requirement by requirement" })).toBeHidden();
  await expect(page.locator(".next-steps .improvement-card")).toHaveCount(3);
  await expect(page.locator(".next-steps .improvement-guide[open]")).toHaveCount(0);
  await page.locator(".next-steps .improvement-guide summary").first().click();
  await expect(page.locator(".next-steps .improvement-guide[open]")).toHaveCount(1);
  await expect(page.getByText("Try this structure").first()).toBeVisible();
  await page.getByRole("tab", { name: "Evidence", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Requirement by requirement" })).toBeVisible();
  expect(await page.locator(".requirement-card").count()).toBeLessThanOrEqual(6);
  await expect(page.locator(".requirement-detail")).toHaveCount(0);
  const first = page.locator(".requirement-toggle").first();
  await first.click();
  await expect(page.locator(".requirement-detail")).toHaveCount(1);
  await first.click();
  await expect(page.locator(".requirement-detail")).toHaveCount(0);
  await page.setViewportSize({ width: 320, height: 900 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  await page.getByRole("tab", { name: "Document insights" }).click();
  await expect(page.getByRole("heading", { name: /Four readings/ })).toBeVisible();
  await expect(page.locator(".assessment-metrics[open]")).toHaveCount(0);
  await page.getByRole("tab", { name: "Document insights" }).press("Home");
  await expect(page.getByRole("tab", { name: "Next steps", exact: true })).toBeFocused();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: "Evidence", exact: true })).toBeFocused();
  await page.getByRole("tab", { name: "Evidence", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Requirement by requirement" })).toBeVisible();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: /^Suggestions/ })).toHaveAttribute(
    "aria-selected",
    "true",
  );
});

test("public navigation supports desktop disclosure and a keyboard-operable mobile menu", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/demo");
  const explore = page.locator(".site-nav-dropdown > summary");
  await explore.click();
  await expect(
    page
      .getByRole("navigation", { name: "Main", exact: true })
      .getByRole("link", { name: /View example/ }),
  ).toBeVisible();
  await explore.press("Escape");
  await expect(page.locator(".site-nav-dropdown")).not.toHaveAttribute("open");
  await expect(explore).toBeFocused();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("navigation", { name: "Main", exact: true })).toBeHidden();
  await page.getByRole("button", { name: "Open navigation" }).click();
  await expect(page.getByRole("button", { name: "Close navigation" })).toHaveAttribute(
    "aria-expanded",
    "true",
  );
  await explore.click();
  await page.addScriptTag({ content: axe.source });
  const issues = await page.evaluate(async () =>
    (
      await (window as typeof window & { axe: typeof axe }).axe.run(document, {
        runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21aa"] },
      })
    ).violations.map((v) => ({ id: v.id, nodes: v.nodes.map((n) => n.target) })),
  );
  expect(issues).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  await explore.press("Escape");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("button", { name: "Open navigation" })).toBeFocused();
  await page.getByRole("button", { name: "Open navigation" }).click();
  await explore.click();
  await page
    .getByRole("navigation", { name: "Main", exact: true })
    .getByRole("link", { name: /^Privacy/ })
    .click();
  await expect(page).toHaveURL(/\/privacy$/);
  await expect(page.getByRole("navigation", { name: "Main", exact: true })).toBeHidden();
  await expect(page.getByRole("link", { name: "Engineering", exact: true })).toHaveCount(0);
  expect((await page.request.get("/engineering")).status()).toBe(404);
});
