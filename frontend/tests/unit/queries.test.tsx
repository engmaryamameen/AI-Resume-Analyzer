import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useQuery } from "@/lib/hooks";

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((yes) => {
    resolve = yes;
  });
  return { promise, resolve };
}

describe("query identity and cancellation", () => {
  it("hides the old page immediately, aborts it, and ignores its late result", async () => {
    const first = deferred<string>();
    const second = deferred<string>();
    const signals: AbortSignal[] = [];
    const { result, rerender, unmount } = renderHook(
      ({ page }) =>
        useQuery(["resumes", page], (signal) => {
          signals.push(signal);
          return page === 0 ? first.promise : second.promise;
        }),
      { initialProps: { page: 0 } },
    );
    await act(async () => {
      await Promise.resolve();
    });
    rerender({ page: 1 });
    expect(result.current.data).toBeNull();
    expect(result.current.loading).toBe(true);
    expect(signals[0]?.aborted).toBe(true);
    await act(async () => {
      second.resolve("second");
    });
    expect(result.current.data).toBe("second");
    await act(async () => {
      first.resolve("first");
    });
    expect(result.current.data).toBe("second");
    unmount();
    expect(signals[1]?.aborted).toBe(true);
  });

  it("keeps same-key data with an explicit refreshing state and recovers after errors", async () => {
    let attempt = 0;
    const pending = deferred<string>();
    const { result } = renderHook(() =>
      useQuery(["item", 1], async () => {
        attempt++;
        if (attempt === 1) return "initial";
        if (attempt === 2) throw new Error("offline");
        return pending.promise;
      }),
    );
    await waitFor(() => expect(result.current.data).toBe("initial"));
    act(() => result.current.reload());
    await waitFor(() => expect(result.current.error).toBeInstanceOf(Error));
    act(() => result.current.reload());
    expect(result.current.refreshing).toBe(true);
    expect(result.current.data).toBe("initial");
    await act(async () => {
      pending.resolve("updated");
    });
    expect(result.current.data).toBe("updated");
    expect(result.current.error).toBeNull();
  });
});

it("does not let a polling reload continually abort a slow current query", async () => {
  const pending = deferred<string>();
  let calls = 0;
  const { result } = renderHook(() =>
    useQuery(["slow"], () => {
      calls++;
      return pending.promise;
    }),
  );
  await act(async () => {
    await Promise.resolve();
  });
  act(() => {
    result.current.reload();
    result.current.reload();
  });
  expect(calls).toBe(1);
  await act(async () => {
    pending.resolve("finished");
  });
  expect(result.current.data).toBe("finished");
});

it("coalesces mutation invalidations while an older list read is pending", async () => {
  const old = deferred<string[]>();
  let calls = 0;
  const { result } = renderHook(() =>
    useQuery(["list"], async () => (++calls === 1 ? old.promise : ["uploaded résumé"])),
  );
  await waitFor(() => expect(calls).toBe(1));
  act(() => {
    result.current.reload();
    result.current.reload();
  });
  expect(calls).toBe(1);
  await act(async () => {
    old.resolve([]);
  });
  await waitFor(() => expect(result.current.data).toEqual(["uploaded résumé"]));
  expect(calls).toBe(2);
});

it("does not discard a queued invalidation when the old read fails", async () => {
  let rejectOld!: (error: Error) => void;
  let calls = 0;
  const old = new Promise<string>((_, reject) => {
    rejectOld = reject;
  });
  const { result } = renderHook(() =>
    useQuery(["recover"], () => (++calls === 1 ? old : Promise.resolve("fresh"))),
  );
  await waitFor(() => expect(calls).toBe(1));
  act(() => result.current.reload());
  await act(async () => {
    rejectOld(new Error("stale read failed"));
  });
  await waitFor(() => expect(result.current.data).toBe("fresh"));
  expect(calls).toBe(2);
  expect(result.current.error).toBeNull();
});
