import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Billing from "@/app/app/billing/page";
const mocks = vi.hoisted(() => ({ status: vi.fn(), checkout: vi.fn(), returned: "" }));
vi.mock("@/features/billing/api", () => ({ billingApi: mocks }));
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(mocks.returned) }));
const state = {
  enabled: true,
  test_mode: true,
  credits: 0,
  pack_credits: 5,
  pack_cents: 500,
  currency: "usd",
};
beforeEach(() => {
  vi.clearAllMocks();
  mocks.returned = "";
  mocks.status.mockResolvedValue(state);
});
describe("review credits", () => {
  it("keeps local use free and disables an unconfigured checkout", async () => {
    mocks.status.mockResolvedValue({ ...state, enabled: false });
    render(<Billing />);
    expect(await screen.findByText(/Reviews are currently free/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open Stripe test checkout" })).toBeDisabled();
    expect(mocks.checkout).not.toHaveBeenCalled();
  });
  it("keeps configured checkout available while reviews are free", async () => {
    mocks.status.mockResolvedValue({ ...state, require_credits: false });
    render(<Billing />);
    expect(await screen.findByText(/Reviews are currently free/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open Stripe test checkout" })).toBeEnabled();
    expect(screen.queryByText(/checkout is unavailable/i)).not.toBeInTheDocument();
  });
  it("keeps the checkout key across a network failure and rejects an unsafe redirect", async () => {
    const user = userEvent.setup();
    mocks.checkout
      .mockRejectedValueOnce(new Error("Connection lost"))
      .mockResolvedValueOnce({ url: "https://unexpected.example/checkout" });
    render(<Billing />);
    const button = await screen.findByRole("button", { name: "Open Stripe test checkout" });
    await user.click(button);
    await waitFor(() => expect(button).toBeEnabled());
    await user.click(button);
    await screen.findByText(/Something unexpected happened/);
    await waitFor(() => expect(button).toBeEnabled());
    expect(mocks.checkout.mock.calls).toHaveLength(2);
    expect(mocks.checkout.mock.calls[0]?.[0]).toBe(mocks.checkout.mock.calls[1]?.[0]);
  });
  it("does not treat a checkout return parameter as purchased credits", async () => {
    mocks.returned = "checkout=returned";
    render(<Billing />);
    expect(await screen.findByText(/redirect alone does not add credits/)).toBeInTheDocument();
    expect(screen.getByText("0")).toBeInTheDocument();
    expect(mocks.checkout).not.toHaveBeenCalled();
  });
});
