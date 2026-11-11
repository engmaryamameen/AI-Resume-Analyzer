import { StrictMode } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { AccountLinkForm } from "@/features/auth/components/account-link-form";
import { authApi } from "@/features/auth/api";

afterEach(() => {
  vi.restoreAllMocks();
  window.history.replaceState(null, "", "/");
});

it("verification establishes the mailbox owner's password and clears the token fragment", async () => {
  const token = "a".repeat(43);
  window.history.replaceState(null, "", `/verify-email#token=${token}`);
  const verify = vi.spyOn(authApi, "verifyEmail").mockResolvedValue();
  render(<AccountLinkForm mode="verify-email" />);
  await userEvent.type(
    await screen.findByLabelText("New password"),
    "mailbox owner password phrase",
  );
  expect(window.location.hash).toBe("");
  await userEvent.click(screen.getByRole("button", { name: "Verify email" }));
  await waitFor(() => expect(verify).toHaveBeenCalledWith(token, "mailbox owner password phrase"));
  expect(await screen.findByText(/Sign in with the password you just chose/)).toBeInTheDocument();
});

it.each(["reset-password", "verify-email"] as const)(
  "preserves a %s link during Strict Mode replay",
  async (mode) => {
    const token = "b".repeat(43);
    window.history.replaceState(null, "", `/${mode}?source=email#token=${token}`);
    const request = vi
      .spyOn(authApi, mode === "reset-password" ? "resetPassword" : "verifyEmail")
      .mockResolvedValue();
    render(
      <StrictMode>
        <AccountLinkForm mode={mode} />
      </StrictMode>,
    );
    await userEvent.type(
      await screen.findByLabelText("New password"),
      "mailbox owner password phrase",
    );
    expect(window.location.hash).toBe("");
    expect(window.location.search).toBe("?source=email");
    await userEvent.click(
      screen.getByRole("button", {
        name: mode === "reset-password" ? "Reset password" : "Verify email",
      }),
    );
    await waitFor(() =>
      expect(request).toHaveBeenCalledWith(token, "mailbox owner password phrase"),
    );
  },
);
