"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export interface AsyncState<T> {
  data: T | null;
  error: unknown;
  loading: boolean;
  refreshing: boolean;
  reload: () => void;
}

type QueryKey = readonly (string | number | boolean | null | undefined)[];

/** Data belongs to one explicit key; a different key never exposes the previous result. */
export function useQuery<T>(
  queryKey: QueryKey,
  queryFn: (signal: AbortSignal) => Promise<T>,
): AsyncState<T> {
  const key = JSON.stringify(queryKey);
  const [result, setResult] = useState<{
    key: string;
    data: T | null;
    error: unknown;
    pending: boolean;
  }>({ key, data: null, error: null, pending: true });
  const [tick, setTick] = useState(0);
  const pendingRef = useRef(false);
  const invalidated = useRef(false);
  const loadRef = useRef(queryFn);
  loadRef.current = queryFn;
  useEffect(() => {
    const controller = new AbortController();
    pendingRef.current = true;
    function settled() {
      pendingRef.current = false;
      if (invalidated.current) {
        invalidated.current = false;
        setTick((value) => value + 1);
      }
    }
    setResult((previous) => ({
      key,
      data: previous.key === key ? previous.data : null,
      error: null,
      pending: true,
    }));
    Promise.resolve()
      .then(() => {
        if (controller.signal.aborted) throw controller.signal.reason;
        return loadRef.current(controller.signal);
      })
      .then(
        (data) => {
          if (!controller.signal.aborted) {
            settled();
            setResult({ key, data, error: null, pending: false });
          }
        },
        (error) => {
          if (!controller.signal.aborted) {
            settled();
            setResult((previous) => ({
              key,
              data: previous.key === key ? previous.data : null,
              error,
              pending: false,
            }));
          }
        },
      );
    return () => {
      controller.abort();
      pendingRef.current = false;
      invalidated.current = false;
    };
  }, [key, tick]);
  const reload = useCallback(() => {
    // A mutation can finish after this read took its snapshot. Do not lose its invalidation.
    if (pendingRef.current) invalidated.current = true;
    else setTick((value) => value + 1);
  }, []);
  const current = result.key === key;
  return {
    data: current ? result.data : null,
    error: current ? result.error : null,
    loading: !current || (result.pending && result.data === null),
    refreshing: current && result.pending && result.data !== null,
    reload,
  };
}

/** Re-runs `reload` every `ms` while `active` is true (used while a file or analysis is processing). */
export function usePolling(active: boolean, reload: () => void, ms = 1500): void {
  useEffect(() => {
    if (!active) return;
    const id = setInterval(reload, ms);
    return () => clearInterval(id);
  }, [active, reload, ms]);
}
