import { afterEach, describe, expect, it, vi } from "vitest";
import { analysesApi } from "@/features/analyses/api";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("request recovery", () => {
  it("recovers an interrupted read without user intervention", async () => {
    vi.useFakeTimers();
    const data = { items: [], total: 0, limit: 20, offset: 0 };
    const fetch = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("connection reset"))
      .mockResolvedValueOnce(Response.json(data));
    vi.stubGlobal("fetch", fetch);
    const result = analysesApi.analyses();
    await vi.runAllTimersAsync();
    await expect(result).resolves.toEqual(data);
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("does not automatically repeat a write request", async () => {
    const fetch = vi.fn().mockRejectedValue(new TypeError("connection reset"));
    vi.stubGlobal("fetch", fetch);
    await expect(analysesApi.createAnalysis("resume", "role", "request-key")).rejects.toMatchObject(
      {
        code: "network_error",
      },
    );
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});

describe("response contracts and caller cancellation", () => {
  it.each([
    new Response("<html>proxy error</html>", { headers: { "Content-Type": "text/html" } }),
    new Response("{bad", { headers: { "Content-Type": "application/json" } }),
    Response.json({ items: "wrong", total: 0, offset: 0, limit: 20 }),
  ])("rejects invalid successful responses", async (response) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));
    await expect(analysesApi.analyses()).rejects.toMatchObject({ code: "invalid_response" });
  });

  it("aborts retry backoff without another fetch or a network error", async () => {
    const fetch = vi.fn().mockRejectedValue(new TypeError("offline"));
    vi.stubGlobal("fetch", fetch);
    const controller = new AbortController();
    const promise = analysesApi.analyses(0, controller.signal);
    await Promise.resolve();
    controller.abort();
    await expect(promise).rejects.toMatchObject({ name: "AbortError" });
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});

it("enforces the guest state schema instead of accepting arbitrary objects", async () => {
  const { validateResponse } = await import("@/lib/contracts");
  expect(validateResponse("/guest", "GET", 200, {})).toBe(false);
  expect(validateResponse("/guest", "GET", 200, { available: "invalid", status: 123 })).toBe(false);
  expect(
    validateResponse("/guest", "GET", 200, {
      available: true,
      status: "idle",
      next_allowed_at: null,
      report: null,
      error_code: null,
    }),
  ).toBe(true);
});
