import { StrictMode } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { AccountLinkForm } from "@/features/auth/components/account-link-form";
import { ApiError } from "@/lib/http/client";
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

it.each(["reset-password", "verify-email"] as const)(
  "accepts an eight-character password for %s",
  async (mode) => {
    const token = "c".repeat(43);
    window.history.replaceState(null, "", `/${mode}#token=${token}`);
    const request = vi
      .spyOn(authApi, mode === "reset-password" ? "resetPassword" : "verifyEmail")
      .mockResolvedValue();
    const user = userEvent.setup();
    render(<AccountLinkForm mode={mode} />);
    const input = await screen.findByLabelText("New password");
    await user.type(input, "Lime#42");
    await user.click(
      screen.getByRole("button", {
        name: mode === "reset-password" ? "Reset password" : "Verify email",
      }),
    );
    expect(request).not.toHaveBeenCalled();
    await user.type(input, "7");
    await user.click(
      screen.getByRole("button", {
        name: mode === "reset-password" ? "Reset password" : "Verify email",
      }),
    );
    await waitFor(() => expect(request).toHaveBeenCalledWith(token, "Lime#427"));
  },
);

it("keeps recovery editable when the account does not exist", async () => {
  vi.spyOn(authApi, "forgotPassword").mockRejectedValue(
    new ApiError(422, "account_not_found", "Missing account"),
  );
  render(<AccountLinkForm mode="forgot-password" />);
  await userEvent.type(screen.getByLabelText("Email"), "missing@example.test");
  await userEvent.click(screen.getByRole("button", { name: "Send email link" }));
  expect(await screen.findByText(/No account exists with this email address/)).toBeInTheDocument();
  expect(screen.getByLabelText("Email")).toHaveValue("missing@example.test");
  expect(screen.queryByText("Check your inbox")).not.toBeInTheDocument();
});

it("identifies the recovery address and lets the user retry", async () => {
  const send = vi.spyOn(authApi, "forgotPassword").mockResolvedValue();
  render(<AccountLinkForm mode="forgot-password" />);
  await userEvent.type(screen.getByLabelText("Email"), "owner@example.test");
  await userEvent.click(screen.getByRole("button", { name: "Send email link" }));
  expect(await screen.findByText("Check your inbox")).toBeInTheDocument();
  expect(screen.getByText(/requested for owner@example.test/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Try again or use another email" }));
  expect(screen.getByLabelText("Email")).toHaveValue("owner@example.test");
  expect(send).toHaveBeenCalledTimes(1);
});
