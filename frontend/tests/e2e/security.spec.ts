import { expect, test } from "@playwright/test";

test("CSP uses a fresh nonce and the real application hydrates", async ({ page, request }) => {
  const first = await request.get("/login");
  const second = await request.get("/login");
  const policy = first.headers()["content-security-policy"] ?? "";
  expect(policy).toContain("'strict-dynamic'");
  expect(policy.split(";").find((directive) => directive.includes("script-src"))).not.toContain(
    "unsafe-inline",
  );
  expect(policy).not.toBe(second.headers()["content-security-policy"]);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/login");
  await page.getByRole("button", { name: "Show password" }).click();
  await expect(page.getByLabel("Password", { exact: true })).toHaveAttribute("type", "text");
  expect(errors).toEqual([]);
});

test("recovery and verification forms remain keyboard accessible", async ({ page }) => {
  await page.goto("/forgot-password");
  await expect(page.getByRole("heading", { name: "Recover your account" })).toBeVisible();
  await expect(page.getByLabel("Email")).toHaveAttribute("type", "email");
  await page.goto("/reset-password");
  await expect(page.getByRole("button", { name: "Reset password" })).toBeDisabled();
  await expect(page.getByRole("link", { name: "Request a new link" })).toBeVisible();
  await page.goto(`/verify-email#token=${"a".repeat(43)}`);
  await expect(page.getByLabel("New password")).toBeVisible();
  await expect(page).toHaveURL(/\/verify-email$/);
});
