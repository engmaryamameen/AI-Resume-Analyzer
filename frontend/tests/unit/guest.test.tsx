import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { GuestAnalyzer } from "@/components/guest-analyzer";
import { api } from "@/lib/api";
import type { GuestState } from "@/lib/types";

const idle: GuestState = {
  available: true,
  next_allowed_at: null,
  status: "idle",
  error_code: null,
  report: null,
};
const completed: GuestState = {
  ...idle,
  available: false,
  status: "succeeded",
  report: {
    id: "review-12345678",
    status: "succeeded",
    resume_version_id: "resume-v1",
    resume_document_id: "resume-1",
    resume_version_no: 1,
    jd_version_id: "role-v1",
    latest_resume_version_id: "resume-v1",
    latest_jd_version_id: "role-v1",
    pipeline_version: "rules-v1",
    engine: { mode: "rules", models: [], calibrated: false, fingerprint: "rules", notes: [] },
    error_code: null,
    created_at: "2026-10-31T09:00:00Z",
    completed_at: "2026-10-31T09:00:03Z",
    staleness: { is_stale: false, reasons: [] },
    assessments: [],
    warnings: [],
    recommendations: [],
    limitations: [],
    matches: [],
    mentions: [],
  },
};
afterEach(() => vi.restoreAllMocks());

describe("guest review state and report clarity", () => {
  it("shows a recoverable service error instead of implying that a free review is available", async () => {
    vi.spyOn(api, "guestStatus")
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(idle);
    render(<GuestAnalyzer />);
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.queryByLabelText("Your résumé file")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByLabelText("Your résumé file")).toBeInTheDocument();
  });

  it("uses one report heading with provenance and the correct editing-plan introduction", async () => {
    vi.spyOn(api, "guestStatus").mockResolvedValue(completed);
    render(<GuestAnalyzer />);
    expect(
      await screen.findByRole("heading", { name: "Your résumé review", level: 1 }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByText(/Start with your editing plan/)).toBeInTheDocument();
    expect(screen.getByText("Résumé version 1")).toBeInTheDocument();
    expect(screen.getByText("Local rule-based reader")).toBeInTheDocument();
    expect(screen.queryByText("Your next chapter starts here")).toBeNull();
    expect(screen.queryByText("A clearer next step.")).toBeNull();
  });

  it("does not delete a report when the visitor cancels the confirmation", async () => {
    vi.spyOn(api, "guestStatus").mockResolvedValue(completed);
    const remove = vi.spyOn(api, "deleteGuest").mockResolvedValue();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<GuestAnalyzer />);
    await userEvent.click(await screen.findByRole("button", { name: "Delete guest report" }));
    expect(confirm).toHaveBeenCalledWith(
      expect.stringContaining("24-hour allowance will not reset"),
    );
    expect(remove).not.toHaveBeenCalled();
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Your résumé review" })).toBeInTheDocument(),
    );
  });
});
