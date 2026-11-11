import { expect, test } from "@playwright/test";

test("navigation is balanced, links underline without a hover pill, and the footer stays compact", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/");
  const nav = page.getByRole("navigation", { name: "Main" });
  const box = (await nav.boundingBox())!;
  expect(Math.abs(box.x + box.width / 2 - 720)).toBeLessThan(12);
  const brand = (await page.locator(".site-topbar .brand-lockup").boundingBox())!;
  const cta = (await page.locator(".site-header-cta").boundingBox())!;
  expect(brand.x).toBeLessThan(box.x);
  expect(cta.x).toBeGreaterThan(box.x + box.width);
  const pricing = nav.getByRole("link", { name: "Pricing", exact: true });
  await pricing.hover();
  await expect(pricing).toHaveCSS("background-color", "rgba(0, 0, 0, 0)");
  await expect(pricing).toHaveCSS("color", "rgb(171, 245, 101)");
  await expect
    .poll(() => pricing.evaluate((el) => getComputedStyle(el, "::after").transform))
    .toBe("matrix(1, 0, 0, 1, 0, 0)");
  expect((await page.locator(".site-footer").boundingBox())!.height).toBeLessThan(110);
});

test("FAQ expands and collapses through intermediate heights and respects reduced motion", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1000, height: 900 });
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.goto("/");
  const summary = page.locator("summary").filter({ hasText: "What powers the analysis?" });
  const details = summary.locator("..");
  const closed = (await details.boundingBox())!.height;
  await summary.click();
  await page.waitForTimeout(65);
  const opening = (await details.boundingBox())!.height;
  await page.waitForTimeout(300);
  const opened = (await details.boundingBox())!.height;
  expect(opening).toBeGreaterThan(closed);
  expect(opening).toBeLessThan(opened);
  await summary.click();
  await page.waitForTimeout(65);
  const closing = (await details.boundingBox())!.height;
  expect(closing).toBeGreaterThan(closed);
  expect(closing).toBeLessThan(opened);
  await page.waitForTimeout(300);
  expect(Math.abs((await details.boundingBox())!.height - closed)).toBeLessThan(2);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await summary.click();
  await page.waitForTimeout(50);
  expect((await details.boundingBox())!.height).toBeCloseTo(opened, 0);
});

test("guest list icons align with their text and upload headings keep their component size", async ({
  page,
}) => {
  await page.route("**/api/v1/guest", (route) =>
    route.fulfill({
      json: {
        available: true,
        next_allowed_at: null,
        status: "idle",
        report: null,
        error_code: null,
      },
    }),
  );
  for (const width of [390, 900, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto("/");
    await page.evaluate(() => document.fonts.ready);
    await page.locator(".review-requirements").scrollIntoViewIfNeeded();
    const list = page.locator(".review-requirements");
    await expect(list).toHaveCSS("list-style-type", "none");
    for (const li of await list.locator("li").all()) {
      const { icon, text } = await li.evaluate((el) => ({
        icon: el.querySelector("svg")!.getBoundingClientRect().toJSON(),
        text: el.querySelector("span")!.getBoundingClientRect().toJSON(),
      }));
      expect(text.x - icon.x - icon.width).toBeGreaterThanOrEqual(8);
      expect(Math.abs(text.y - icon.y)).toBeLessThan(8);
    }
    expect(
      Number.parseFloat(
        await page
          .getByRole("heading", { name: "Let’s start with your résumé." })
          .evaluate((el) => getComputedStyle(el).fontSize),
      ),
    ).toBeLessThanOrEqual(24);
  }
});
