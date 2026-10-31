"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export interface AsyncState<T> {
  data: T | null;
  error: unknown;
  loading: boolean;
  reload: () => void;
}

export function useAsync<T>(load: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  const hasData = useRef(false);
  const loadRef = useRef(load);
  loadRef.current = load;

  useEffect(() => {
    let cancelled = false; // background reloads keep the current data visible instead of flashing
    loadRef.current().then(
      (v) => {
        if (!cancelled) {
          hasData.current = true;
          setData(v);
          setError(null);
          setLoading(false);
        }
      },
      (e) => {
        if (!cancelled) {
          setError(e);
          setLoading(false);
        }
      },
    );
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  const reload = useCallback(() => {
    setError(null);
    setLoading(!hasData.current);
    setTick((t) => t + 1);
  }, []);
  return { data, error, loading, reload };
}

/** Re-runs `reload` every `ms` while `active` is true (used while a file or analysis is processing). */
export function usePolling(active: boolean, reload: () => void, ms = 1500): void {
  useEffect(() => {
    if (!active) return;
    const id = setInterval(reload, ms);
    return () => clearInterval(id);
  }, [active, reload, ms]);
}
