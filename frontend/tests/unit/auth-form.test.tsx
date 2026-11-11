import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { AuthForm } from "@/features/auth/components/auth-form";
import { authApi } from "@/features/auth/api";

const navigation = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => navigation }));
afterEach(() => vi.restoreAllMocks());

it("rejects seven characters and submits eight characters for registration", async () => {
  const register = vi.spyOn(authApi, "register").mockResolvedValue({
    user: null,
    email_verification_required: true,
  });
  const user = userEvent.setup();
  render(<AuthForm mode="register" />);
  await user.type(screen.getByLabelText("Email"), "boundary@example.test");
  const password = screen.getByLabelText("Password", { exact: true });
  await user.type(password, "Lime#42");
  await user.click(screen.getByRole("button", { name: "Create account" }));
  expect(screen.getByText("Use at least 8 characters.")).toBeInTheDocument();
  expect(register).not.toHaveBeenCalled();
  await user.type(password, "7");
  await user.click(screen.getByRole("button", { name: "Create account" }));
  await waitFor(() => expect(register).toHaveBeenCalledWith("boundary@example.test", "Lime#427"));
  expect(navigation.push).toHaveBeenCalledWith("/verify-email");
});
