import { describe, expect, it } from "vitest";
import { guestReducer } from "@/features/guest/state";
import type { GuestState } from "@/lib/types";
const idle: GuestState = {
  status: "idle",
  available: true,
  next_allowed_at: null,
  report: null,
  error_code: null,
};

describe("guest lifecycle invariants", () => {
  it("never starts a mutation before the initial status check", () => {
    expect(guestReducer({ phase: "checking", guest: null }, { type: "submitting" }).phase).toBe(
      "checking",
    );
  });
  it("cannot clear a pending mutation when a result arrives", () => {
    const view = guestReducer({ phase: "ready", guest: idle }, { type: "submitting" });
    const received = guestReducer(view, {
      type: "received",
      guest: { ...idle, status: "extracting" },
    });
    expect(received.phase).toBe("submitting");
    expect(guestReducer(received, { type: "finished" }).phase).toBe("ready");
  });
  it.each(["preparing", "extracting", "analyzing", "succeeded", "failed", "idle"] as const)(
    "accepts authoritative server status %s after deletion or expiry",
    (status) => {
      const view = guestReducer({ phase: "ready", guest: idle }, { type: "deleting" });
      const next = guestReducer(view, { type: "received", guest: { ...idle, status } });
      expect(next.guest?.status).toBe(status);
      expect(guestReducer(next, { type: "finished" }).phase).toBe("ready");
    },
  );
});
