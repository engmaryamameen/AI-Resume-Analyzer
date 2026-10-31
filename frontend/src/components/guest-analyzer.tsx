"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, ApiError, newIdempotencyKey } from "@/lib/api";
import { failureMessage, formatDateTime, friendlyError } from "@/lib/copy";
import type { GuestState } from "@/lib/types";
import { AnalysisResults } from "./analysis-view";
import { Icon } from "./icon";
import { Button, ButtonLink, ErrorState, Loading, Notice, TextArea } from "./ui";

export function GuestAnalyzer() {
  const [state, setState] = useState<GuestState | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [job, setJob] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  const [step, setStep] = useState<1 | 2>(1);
  const [statusLoading, setStatusLoading] = useState(true);
  const [statusError, setStatusError] = useState<unknown>(null);
  const [statusAttempt, setStatusAttempt] = useState(0);
  const resultHeading = useRef<HTMLHeadingElement>(null);
  const submitted = useRef(false);
  const requestKey = useRef<string | null>(null);
  const [clock, setClock] = useState(Date.now());
  const pending =
    state?.status === "preparing" ||
    state?.status === "extracting" ||
    state?.status === "analyzing";
  useEffect(() => {
    let live = true;
    setStatusLoading(true);
    api
      .guestStatus()
      .then((v) => {
        if (live) {
          setState(v);
          setStatusError(null);
        }
      })
      .catch((e) => {
        if (live) setStatusError(e);
      })
      .finally(() => {
        if (live) setStatusLoading(false);
      });
    return () => {
      live = false;
    };
  }, [statusAttempt]);
  useEffect(() => {
    if (state?.report && submitted.current) {
      submitted.current = false;
      resultHeading.current?.focus();
    }
  }, [state?.report]);
  useEffect(() => {
    if (!pending) return;
    let live = true;
    const id = setInterval(() => {
      api
        .guestProgress()
        .then((v) => {
          if (live) {
            setState(v);
            setError("");
          }
        })
        .catch((e) => {
          if (live) setError(friendlyError(e));
        });
    }, 1800);
    return () => {
      live = false;
      clearInterval(id);
    };
  }, [pending]);
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
    if (!file || busy || pending || blocked) return;
    submitted.current = true;
    setBusy(true);
    setError("");
    requestKey.current ??= newIdempotencyKey();
    try {
      setState(await api.guestAnalyze(file, job, requestKey.current));
    } catch (e) {
      setError(friendlyError(e));
      if (e instanceof ApiError && e.code === "guest_limit") {
        try {
          setState(await api.guestStatus());
        } catch {
          /* Keep the actionable error visible. */
        }
      }
    } finally {
      setBusy(false);
    }
  }
  async function remove() {
    if (
      !window.confirm(
        "Delete this guest report and its documents? Your 24-hour allowance will not reset.",
      )
    )
      return;
    setBusy(true);
    try {
      await api.deleteGuest();
      setState(await api.guestStatus());
      setFile(null);
      requestKey.current = null;
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section
      id="analyze"
      className="review-hero"
      aria-labelledby="guest-title"
      data-result={!!state?.report || undefined}
      data-state={
        state?.report
          ? "report"
          : statusLoading
            ? "checking"
            : statusError
              ? "unavailable"
              : pending
                ? "processing"
                : blocked
                  ? "limited"
                  : "upload"
      }
    >
      {state?.report ? (
        <div className="review-result-intro">
          <div>
            <span className="micro-label">YOUR REVIEW IS READY</span>
            <h1 id="guest-title" ref={resultHeading} tabIndex={-1}>
              Your résumé review
            </h1>
            <p>Start with your editing plan, then explore the evidence behind each finding.</p>
            <div className="review-result-meta">
              <span>
                <Icon name="document" size={14} /> Résumé version{" "}
                {state.report.resume_version_no ?? 1}
              </span>
              <span>
                <Icon name="history" size={14} />{" "}
                {formatDateTime(state.report.completed_at ?? state.report.created_at)}
              </span>
              <span>
                {state.report.engine && state.report.engine.mode !== "rules"
                  ? "Local models"
                  : "Local rule-based reader"}
              </span>
              <span>Guest report · available for 24 hours</span>
            </div>
          </div>
          <Button variant="quiet" onClick={remove} busy={busy}>
            Delete guest report
          </Button>
        </div>
      ) : (
        <div className="review-hero-copy">
          <span className="hero-kicker">
            <span /> A little clarity for your next move
          </span>
          <h1 id="guest-title">
            Your experience.
            <br />
            <em>Its next chapter.</em>
          </h1>
          <p className="review-hero-lead">
            See how your résumé reads against the role you want. Find what’s clear, what’s missing,
            and where to focus.
          </p>
          <div className="review-hero-trust">
            <span>
              <Icon name="shield" size={15} /> Privately processed
            </span>
            <span>
              <Icon name="check" size={15} />{" "}
              {blocked ? "More reviews with an account" : "First review free"}
            </span>
          </div>
          <Link className="review-example-link" href="/demo">
            See an example first <Icon name="arrow" size={16} />
          </Link>
          <div className="hero-margin-note">
            <span className="micro-label">THE DIFFERENCE IS IN THE DETAILS</span>
            <div>
              <span>“Python”</span>
              <Icon name="arrow" size={19} />
              <span>
                “Built billing APIs
                <br />
                in Python.”
              </span>
            </div>
            <p>Your experience, with a little more context.</p>
          </div>
        </div>
      )}
      <div className="guest-workspace">
        {!state?.report && (
          <div className="guest-workspace-heading">
            <span>
              <Icon name="document" size={18} />{" "}
              {blocked
                ? "Your free review allowance"
                : pending
                  ? "Review in progress"
                  : "Your next chapter starts here"}
            </span>
            <span className="guest-allowance">
              {blocked ? "24-HOUR RESET" : pending ? "LOCAL PROCESSING" : "NO ACCOUNT NEEDED"}
            </span>
          </div>
        )}
        {!!error && (
          <div className="mb-5">
            <Notice tone="bad">{error}</Notice>
          </div>
        )}
        {statusLoading ? (
          <Loading label="Checking your free review…" />
        ) : statusError ? (
          <ErrorState error={statusError} onRetry={() => setStatusAttempt((v) => v + 1)} />
        ) : pending ? (
          <div className="guest-progress" role="status">
            <span className="guest-progress-icon">
              <Icon name="search" size={30} />
            </span>
            <h2>
              {state.status === "extracting" ? "Reading your résumé" : "Following the evidence"}
            </h2>
            <p>
              Your document is being processed privately by the local worker. This usually takes a
              few moments.
            </p>
            <div className="guest-progress-track">
              <span />
            </div>
          </div>
        ) : state?.report ? (
          <AnalysisResults {...state.report} />
        ) : blocked ? (
          <div className="guest-limit">
            <span className="guest-limit-icon">
              <Icon name="history" size={27} />
            </span>
            <h2>You’ve used your free review.</h2>
            <p>
              Create a free account to analyze another résumé and keep your versions together, or
              come back when your allowance resets.
            </p>
            <div className="guest-reset">
              <span>Next free analysis</span>
              <strong>
                In {Math.floor(remainingMinutes / 60)}h {remainingMinutes % 60}m
              </strong>
            </div>
            <ButtonLink href="/register">
              Create a free account <Icon name="arrow" size={16} />
            </ButtonLink>
            <p className="guest-network-note">
              The guest allowance is shared by visitors on the same network.
            </p>
          </div>
        ) : (
          <form onSubmit={submit} className="review-form">
            <nav className="review-steps" aria-label="Review setup">
              <button
                type="button"
                aria-current={step === 1 ? "step" : undefined}
                onClick={() => setStep(1)}
              >
                <span>{step === 2 && file ? <Icon name="check" size={12} /> : "1"}</span>Your résumé
              </button>
              <span className="review-step-line" />
              <button
                type="button"
                disabled={!file}
                aria-current={step === 2 ? "step" : undefined}
                onClick={() => setStep(2)}
              >
                <span>2</span>Target role
              </button>
            </nav>
            {state?.status === "failed" && (
              <Notice tone="warn">
                {failureMessage(state.error_code)} Your free allowance has been restored.
              </Notice>
            )}
            {step === 1 ? (
              <div className="review-step-content">
                <div className="review-step-heading">
                  <h2>Let’s start with your résumé.</h2>
                  <p>The version you have right now is a good place to begin.</p>
                </div>
                <div
                  className={`guest-upload ${dragging ? "is-dragging" : ""} ${file ? "has-file" : ""}`}
                  onDragOver={(e) => {
                    e.preventDefault();
                    if (!busy) setDragging(true);
                  }}
                  onDragLeave={() => setDragging(false)}
                  onDrop={(e) => {
                    e.preventDefault();
                    setDragging(false);
                    if (e.dataTransfer.files.length > 1) {
                      setError("Please choose one résumé at a time.");
                      return;
                    }
                    pick(e.dataTransfer.files[0]);
                  }}
                >
                  <span className="upload-illustration">
                    <Icon name={file ? "document" : "upload"} size={28} />
                    {file && (
                      <span>
                        <Icon name="check" size={11} />
                      </span>
                    )}
                  </span>
                  <span className="upload-title">{file ? file.name : "Drop your résumé here"}</span>
                  <p>
                    {file
                      ? `${(file.size / 1024).toFixed(0)} KB · Ready for a closer reading`
                      : "PDF or DOCX · Up to 5 MB"}
                  </p>
                  <label htmlFor="guest-resume" className="upload-browse">
                    {file ? "Choose a different file" : "Browse files"}
                    <Icon name="arrowUpRight" size={14} />
                  </label>
                  <input
                    id="guest-resume"
                    className="guest-file-input"
                    type="file"
                    aria-label="Your résumé file"
                    accept=".pdf,.docx"
                    disabled={busy}
                    onChange={(e) => pick(e.target.files?.[0])}
                  />
                </div>
                <Button
                  type="button"
                  className="review-continue w-full"
                  disabled={!file || busy}
                  onClick={() => setStep(2)}
                >
                  Continue to target role <Icon name="arrow" size={16} />
                </Button>
              </div>
            ) : (
              <div className="review-step-content">
                <div className="review-step-heading">
                  <h2>Where would you like to go?</h2>
                  <p>Paste the job description for the role you have in mind.</p>
                </div>
                <div className="review-selected-file">
                  <Icon name="document" size={17} />
                  <span>{file?.name}</span>
                  <button type="button" onClick={() => setStep(1)} disabled={busy}>
                    Change
                  </button>
                </div>
                <TextArea
                  label="Target job description"
                  rows={6}
                  maxLength={20000}
                  minLength={40}
                  required
                  disabled={busy}
                  placeholder="Paste the role’s responsibilities and requirements…"
                  value={job}
                  onChange={(e) => {
                    setJob(e.target.value);
                    requestKey.current = null;
                  }}
                />
                <Button
                  type="submit"
                  className="review-continue w-full"
                  busy={busy}
                  disabled={!file || job.trim().length < 40}
                >
                  Analyze my résumé for free <Icon name="arrow" size={16} />
                </Button>
                <button
                  type="button"
                  className="review-back"
                  onClick={() => setStep(1)}
                  disabled={busy}
                >
                  <Icon name="arrowLeft" size={14} /> Back to your résumé
                </button>
              </div>
            )}
            <div className="review-form-footer">
              <Icon name="shield" size={13} />
              <span>Stays on this server. No outside AI service.</span>
            </div>
            <p className="guest-footnote">
              One free review per network every 24 hours.{" "}
              <Link href="/privacy">Privacy details</Link>
            </p>
          </form>
        )}

        {state?.report && (
          <div className="guest-account-invite">
            <div>
              <strong>Make room for your next revision.</strong>
              <p>
                Create an account to run more analyses and keep your history. Guest reports are
                temporary and are not moved into your account.
              </p>
            </div>
            <ButtonLink href="/register">
              Create account <Icon name="arrow" size={15} />
            </ButtonLink>
          </div>
        )}
      </div>
    </section>
  );
}
