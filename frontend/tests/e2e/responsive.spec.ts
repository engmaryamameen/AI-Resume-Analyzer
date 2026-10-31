import { expect, test } from "@playwright/test";
import axe from "axe-core";

// Isolate visual states without consuming the real guest allowance or creating documents.
for (const state of ["upload", "limited", "processing"] as const) {
  test(`home layout remains balanced across intermediate widths in the ${state} state`, async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    const fixture = {
      available: state === "upload",
      next_allowed_at: state === "upload" ? null : new Date(Date.now() + 86_400_000).toISOString(),
      status: state === "processing" ? "extracting" : "idle",
      error_code: null,
      report: null,
    };
    await page.route("**/api/v1/guest", (route) => route.fulfill({ json: fixture }));
    await page.route("**/api/v1/guest/progress", (route) => route.fulfill({ json: fixture }));
    for (const width of [320, 390, 600, 768, 820, 900, 960, 1024, 1280, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      await page.goto("/");
      await expect(page.locator(`.review-hero[data-state="${state}"]`)).toBeVisible();
      await page.evaluate(() => document.fonts.ready);
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
        `${state} at ${width}px`,
      ).toBe(true);
      const copy = (await page.locator(".review-hero-copy").boundingBox())!;
      const card = (await page.locator(".guest-workspace").boundingBox())!;
      if (width <= 960)
        expect(card.y, `stacked ${state} at ${width}px`).toBeGreaterThanOrEqual(
          copy.y + copy.height,
        );
      else expect(Math.abs(copy.y - card.y), `top-aligned ${state} at ${width}px`).toBeLessThan(3);
      if (state === "limited") {
        const note = (await page.locator(".guest-network-note").boundingBox())!;
        expect(
          card.y + card.height - (note.y + note.height),
          `bottom whitespace at ${width}px`,
        ).toBeLessThan(56);
      }
      if ([320, 900, 1440].includes(width)) {
        await page.addScriptTag({ content: axe.source });
        const issues = await page.evaluate(async () =>
          (
            await (window as typeof window & { axe: typeof axe }).axe.run(document, {
              runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21aa"] },
            })
          ).violations.map((v) => ({ id: v.id, targets: v.nodes.map((n) => n.target) })),
        );
        expect(issues, `${state} at ${width}px`).toEqual([]);
      }
      if (state === "limited" && [900, 1280].includes(width))
        await page.screenshot({
          path: test.info().outputPath(`limited-${width}.png`),
          fullPage: true,
          animations: "disabled",
        });
    }
  });
}
