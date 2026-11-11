import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { GuestAnalyzer } from "@/features/guest/guest-analyzer";
import { guestApi as api } from "@/features/guest/api";
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
  it("opens optional role context without submitting the résumé", async () => {
    vi.spyOn(api, "guestStatus").mockResolvedValue(idle);
    const analyze = vi.spyOn(api, "guestAnalyze").mockResolvedValue(idle);
    const user = userEvent.setup();
    render(<GuestAnalyzer />);
    await user.upload(
      await screen.findByLabelText("Your résumé file"),
      new File(["synthetic document"], "resume.pdf", { type: "application/pdf" }),
    );
    await user.click(screen.getByRole("button", { name: "Add a target role (optional)" }));
    expect(await screen.findByLabelText("Target job description")).toBeEnabled();
    expect(analyze).not.toHaveBeenCalled();
  });

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

  it("preserves the page heading when the analyzer is embedded in the landing page", async () => {
    vi.spyOn(api, "guestStatus").mockResolvedValue(idle);
    render(
      <main>
        <h1>Résumé analysis</h1>
        <GuestAnalyzer headingLevel={2} />
      </main>,
    );
    expect(await screen.findByLabelText("Your résumé file")).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(
      screen.getByRole("heading", { name: "Review your résumé.", level: 2 }),
    ).toBeInTheDocument();
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

describe("guest progress polling", () => {
  it("does not start a second progress request while the first is unresolved", async () => {
    const extracting: GuestState = { ...idle, status: "extracting", available: false };
    vi.spyOn(api, "guestStatus").mockResolvedValue(extracting);
    let resolveProgress: ((state: GuestState) => void) | undefined;
    const progress = vi.spyOn(api, "guestProgress").mockImplementation(
      () =>
        new Promise<GuestState>((resolve) => {
          resolveProgress = resolve;
        }),
    );
    vi.useFakeTimers();
    try {
      render(<GuestAnalyzer />);
      await act(async () => {
        await Promise.resolve();
      });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1800);
      });
      expect(progress).toHaveBeenCalledTimes(1);
      await act(async () => {
        await vi.advanceTimersByTimeAsync(6000);
      });
      expect(progress).toHaveBeenCalledTimes(1);
      await act(async () => {
        resolveProgress?.(extracting);
      });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1800);
      });
      expect(progress).toHaveBeenCalledTimes(2);
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("guest request identity", () => {
  it("keeps an identical retry key and changes it when the job payload changes", async () => {
    const { renderHook } = await import("@testing-library/react");
    const { useGuestAnalysis } = await import("@/features/guest/use-guest-analysis");
    const { ApiError } = await import("@/lib/http/client");
    vi.spyOn(api, "guestStatus").mockResolvedValue(idle);
    const analyze = vi
      .spyOn(api, "guestAnalyze")
      .mockRejectedValueOnce(new ApiError(0, "network_error", "offline"))
      .mockRejectedValueOnce(new ApiError(422, "invalid_upload", "invalid document"))
      .mockRejectedValue(new ApiError(0, "network_error", "offline"));
    const { result } = renderHook(() => useGuestAnalysis());
    await waitFor(() => expect(result.current.statusLoading).toBe(false));
    act(() => {
      result.current.pick(new File(["document"], "cv.docx"));
      result.current.setJob("Python backend experience for a platform engineering role.");
    });
    const event = { preventDefault() {} } as React.FormEvent;
    await act(async () => {
      await result.current.submit(event);
    });
    await act(async () => {
      await result.current.submit(event);
    });
    expect(analyze.mock.calls[0]?.[2]).toBe(analyze.mock.calls[1]?.[2]);
    act(() => result.current.setJob("Rust backend experience for a platform engineering role."));
    await act(async () => {
      await result.current.submit(event);
    });
    expect(analyze.mock.calls[2]?.[2]).not.toBe(analyze.mock.calls[1]?.[2]);
  });
});

it("recovers an accepted guest POST after its response and cookie are lost", async () => {
  const { renderHook } = await import("@testing-library/react");
  const { useGuestAnalysis } = await import("@/features/guest/use-guest-analysis");
  const { ApiError } = await import("@/lib/http/client");
  vi.spyOn(api, "guestStatus")
    .mockResolvedValueOnce(idle)
    .mockResolvedValue({
      ...idle,
      available: false,
      next_allowed_at: new Date(Date.now() + 86400000).toISOString(),
    });
  const post = vi
    .spyOn(api, "guestAnalyze")
    .mockRejectedValueOnce(new ApiError(0, "network_error", "response lost"))
    .mockResolvedValue({ ...idle, status: "extracting", available: false });
  const { result } = renderHook(() => useGuestAnalysis());
  await waitFor(() => expect(result.current.statusLoading).toBe(false));
  const file = new File(["synthetic"], "resume.docx");
  act(() => {
    result.current.pick(file);
    result.current.setJob("Build and operate Python APIs for a platform team.");
  });
  const event = { preventDefault() {} } as React.FormEvent;
  await act(async () => {
    await result.current.submit(event);
  });
  expect(result.current.recovering).toBe(true);
  expect(result.current.blocked).toBe(false);
  act(() => result.current.setJob("This edit must not replace the uncertain original request."));
  await act(async () => {
    await result.current.submit(event);
  });
  expect(post.mock.calls[1]).toEqual(post.mock.calls[0]);
  expect(result.current.recovering).toBe(false);
  expect(result.current.pending).toBe(true);
});
