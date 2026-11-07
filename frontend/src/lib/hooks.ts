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
  const loadRef = useRef(queryFn);
  loadRef.current = queryFn;
  useEffect(() => {
    const controller = new AbortController();
    pendingRef.current = true;
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
            pendingRef.current = false;
            setResult({ key, data, error: null, pending: false });
          }
        },
        (error) => {
          if (!controller.signal.aborted) {
            pendingRef.current = false;
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
    };
  }, [key, tick]);
  const reload = useCallback(() => {
    if (!pendingRef.current) setTick((value) => value + 1);
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
