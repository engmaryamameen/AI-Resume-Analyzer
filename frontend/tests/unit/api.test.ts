import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api";

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
    const result = api.analyses();
    await vi.runAllTimersAsync();
    await expect(result).resolves.toEqual(data);
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("does not automatically repeat a write request", async () => {
    const fetch = vi.fn().mockRejectedValue(new TypeError("connection reset"));
    vi.stubGlobal("fetch", fetch);
    await expect(api.createAnalysis("resume", "role", "request-key")).rejects.toMatchObject({
      code: "network_error",
    });
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});
