"use client";
import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { guestApi as api } from "./api";
import { ApiError, newIdempotencyKey } from "@/lib/http/client";
import { friendlyError } from "@/lib/copy";
import type { GuestState } from "@/lib/types";
import { guestReducer } from "./state";

export function useGuestAnalysis() {
  const [view, dispatch] = useReducer(guestReducer, { phase: "checking", guest: null });
  const state = view.guest;
  const busy = view.phase === "submitting" || view.phase === "deleting";
  const statusLoading = view.phase === "checking";
  const statusError = view.phase === "unavailable" ? view.error : null;
  const setState = useCallback((guest: GuestState) => dispatch({ type: "received", guest }), []);
  const [file, setFile] = useState<File | null>(null);
  const [job, setJob] = useState("");
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  const [step, setStep] = useState<1 | 2>(1);
  const [statusAttempt, setStatusAttempt] = useState(0);
  const resultHeading = useRef<HTMLHeadingElement>(null);
  const submitted = useRef(false);
  const operation = useRef(false);
  const requestKey = useRef<{ file: File; job: string; key: string } | null>(null);
  const uncertain = useRef(false);
  const requestVersion = useRef(0);
  const [clock, setClock] = useState(Date.now());
  const pending =
    state?.status === "preparing" ||
    state?.status === "extracting" ||
    state?.status === "analyzing";
  useEffect(() => {
    let live = true;
    const version = requestVersion.current;
    const controller = new AbortController();
    dispatch({ type: "checking" });
    api
      .guestStatus(controller.signal)
      .then((v) => {
        if (live && version === requestVersion.current) {
          setState(v);
        }
      })
      .catch((e) => {
        if (live && version === requestVersion.current) dispatch({ type: "unavailable", error: e });
      });
    return () => {
      live = false;
      controller.abort();
    };
  }, [statusAttempt, setState]);
  useEffect(() => {
    if (state?.report && submitted.current) {
      submitted.current = false;
      resultHeading.current?.focus();
    }
  }, [state?.report]);
  useEffect(() => {
    if (!pending || busy) return;
    let live = true;
    const version = requestVersion.current;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const next = await api.guestProgress();
        if (live && version === requestVersion.current) {
          setState(next);
          setError("");
        }
      } catch (e) {
        if (live && version === requestVersion.current) setError(friendlyError(e));
      } finally {
        if (live && version === requestVersion.current) timer = setTimeout(poll, 1800);
      }
    }
    timer = setTimeout(poll, 1800);
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [pending, busy, setState]);
  useEffect(() => {
    const id = setInterval(() => setClock(Date.now()), 60_000);
    return () => clearInterval(id);
  }, []);
  const remaining = state?.next_allowed_at
    ? Math.max(0, new Date(state.next_allowed_at).getTime() - clock)
    : 0;
  const remainingMinutes = Math.ceil(remaining / 60_000);
  const blocked = state?.available === false && remaining > 0;
  function pick(next: File | undefined) {
    if (!next || busy || pending) return;
    if (!/\.(pdf|docx)$/i.test(next.name) || next.size > 5 * 1024 * 1024) {
      setError("Choose a PDF or DOCX résumé, up to 5 MB.");
      return;
    }
    setFile(next);
    setError("");
    requestKey.current = null;
  }
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!file || operation.current || statusLoading || statusError || busy || pending || blocked)
      return;
    operation.current = true;
    if (uncertain.current) {
      dispatch({ type: "submitting" });
      try {
        const current = await api.guestStatus();
        setState(current);
        if (current.status !== "idle" && current.status !== "failed") return;
        uncertain.current = false;
      } catch (error) {
        setError(friendlyError(error));
        return;
      } finally {
        operation.current = false;
        dispatch({ type: "finished" });
      }
    }
    operation.current = true;
    submitted.current = true;
    const version = ++requestVersion.current;
    dispatch({ type: "submitting" });
    setError("");
    if (
      !requestKey.current ||
      requestKey.current.file !== file ||
      requestKey.current.job !== job.trim()
    ) {
      requestKey.current = { file, job: job.trim(), key: newIdempotencyKey() };
    }
    try {
      const result = await api.guestAnalyze(file, job, requestKey.current.key);
      if (version === requestVersion.current) setState(result);
    } catch (e) {
      if (version !== requestVersion.current) return;
      setError(friendlyError(e));
      uncertain.current =
        e instanceof ApiError && ["network_error", "request_timeout"].includes(e.code);
      if (
        e instanceof ApiError &&
        ["guest_limit", "network_error", "request_timeout"].includes(e.code)
      ) {
        try {
          const current = await api.guestStatus();
          if (version === requestVersion.current) {
            setState(current);
            uncertain.current = false;
          }
        } catch {
          /* Keep the actionable error visible. */
        }
      }
    } finally {
      operation.current = false;
      dispatch({ type: "finished" });
    }
  }
  async function remove() {
    if (operation.current) return;
    if (
      !window.confirm(
        "Delete this guest report and its documents? Your 24-hour allowance will not reset.",
      )
    )
      return;
    operation.current = true;
    const version = ++requestVersion.current;
    dispatch({ type: "deleting" });
    try {
      await api.deleteGuest();
      const current = await api.guestStatus();
      if (version === requestVersion.current) {
        setState(current);
        setFile(null);
        requestKey.current = null;
      }
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      operation.current = false;
      dispatch({ type: "finished" });
    }
  }

  return {
    state,
    file,
    job,
    setJob,
    busy,
    error,
    setError,
    dragging,
    setDragging,
    step,
    setStep,
    statusLoading,
    statusError,
    setStatusAttempt,
    resultHeading,
    pending,
    remainingMinutes,
    blocked,
    pick,
    submit,
    remove,
  };
}
