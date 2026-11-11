"use client";
import Link from "next/link";
import { failureMessage, formatDateTime } from "@/lib/copy";
import { AnalysisResults } from "@/features/analyses/components/analysis-report";
import { Icon } from "@/components/icon";
import { Button, ButtonLink, ErrorState, Loading, Notice, TextArea } from "@/components/ui";
import { useGuestAnalysis } from "./use-guest-analysis";

export function GuestAnalyzer({ headingLevel = 1 }: { headingLevel?: 1 | 2 }) {
  const Heading = headingLevel === 1 ? "h1" : "h2";
  const {
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
    recovering,
    pick,
    submit,
    remove,
  } = useGuestAnalysis();
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
            <Heading id="guest-title" ref={resultHeading} tabIndex={-1}>
              Your résumé review
            </Heading>
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
                {state.report.review
                  ? `AI résumé review · ${state.report.review.model}`
                  : state.report.engine && state.report.engine.mode !== "rules"
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
          <span className="hero-kicker">Try the analyzer</span>
          <Heading id="guest-title">Review your résumé.</Heading>
          <p className="review-hero-lead">
            Upload your résumé for a general review, or add a job description for a targeted review.
            Inspect the evidence behind each finding before deciding what to change.
          </p>
          <ul className="review-requirements">
            <li>
              <Icon name="check" size={16} />
              <span>Text-based PDF or DOCX, up to 5 MB.</span>
            </li>
            <li>
              <Icon name="check" size={16} />
              <span>Optional: a job description for a role-specific review.</span>
            </li>
            <li>
              <Icon name="check" size={16} />
              <span>One guest review per network every 24 hours.</span>
            </li>
          </ul>
          <Link className="review-example-link" href="/demo">
            Explore the working demo <Icon name="arrow" size={16} />
          </Link>
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
        {recovering && (
          <div className="mb-4">
            <Notice title="Recover your existing review">
              The response was interrupted. Retry the original request below to recover its private
              access. Your selected file and job description are kept for this retry.
            </Notice>
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
              {state?.status === "extracting" ? "Reading your résumé" : "Following the evidence"}
            </h2>
            <p>
              Your document is being processed privately by the local worker. A local AI review can
              take a few minutes.
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
                    disabled={busy || recovering}
                    onChange={(e) => pick(e.target.files?.[0])}
                  />
                </div>
                <Button
                  type="button"
                  className="review-continue w-full"
                  busy={busy}
                  disabled={!file || recovering}
                  onClick={(event) => submit(event, false)}
                >
                  Review without a job description <Icon name="arrow" size={16} />
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  className="review-continue w-full"
                  disabled={!file || busy}
                  onClick={(event) => {
                    event.preventDefault();
                    setStep(2);
                  }}
                >
                  Add a target role (optional) <Icon name="arrow" size={16} />
                </Button>
              </div>
            ) : (
              <div className="review-step-content">
                <div className="review-step-heading">
                  <h2>Add context, if you have a role in mind.</h2>
                  <p>
                    A job description is optional. Leave it blank to review your résumé on its own.
                  </p>
                </div>
                <div className="review-selected-file">
                  <Icon name="document" size={17} />
                  <span>{file?.name}</span>
                  <button type="button" onClick={() => setStep(1)} disabled={busy || recovering}>
                    Change
                  </button>
                </div>
                <TextArea
                  label="Target job description"
                  rows={6}
                  maxLength={20000}
                  minLength={job.trim() ? 40 : undefined}
                  disabled={busy || recovering}
                  placeholder="Paste the role’s responsibilities and requirements…"
                  value={job}
                  onChange={(e) => {
                    setJob(e.target.value);
                  }}
                />
                <Button
                  type="submit"
                  className="review-continue w-full"
                  busy={busy}
                  disabled={!file || (job.trim().length > 0 && job.trim().length < 40)}
                >
                  {recovering ? "Recover my existing review" : "Analyze my résumé for free"}{" "}
                  <Icon name="arrow" size={16} />
                </Button>
                <button
                  type="button"
                  className="review-back"
                  onClick={() => setStep(1)}
                  disabled={busy || recovering}
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
