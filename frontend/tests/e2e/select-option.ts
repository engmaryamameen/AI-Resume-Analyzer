import type { Locator } from "@playwright/test";
export async function selectOption(control: Locator, choice: { index?: number; label?: string }) {
  await control.click();
  const root = control.page();
  const options = root.getByRole("option");
  if (choice.label) await options.filter({ hasText: choice.label }).first().click();
  else await options.nth(Math.max(0, (choice.index ?? 1) - 1)).click();
}
