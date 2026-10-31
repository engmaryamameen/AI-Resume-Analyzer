"use client";

import { Select } from "@/components/select";

import { useState } from "react";
import Link from "next/link";
import { Icon } from "@/components/icon";
import { AnalysisResults } from "@/components/analysis-view";
import { SiteFooter, SiteHeader } from "@/components/site-header";
import { Button, ErrorState, Notice } from "@/components/ui";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import type { DemoResult } from "@/lib/types";

export default function Demo() {
  const samples = useAsync(() => api.demoSamples(), []);
  const [resume, setResume] = useState("");
  const [job, setJob] = useState("");
  const [result, setResult] = useState<DemoResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function run(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!resume || !job || busy) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.demoAnalyze({ resume_id: resume, job_id: job }));
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <SiteHeader />
      <main id="main" className="mx-auto min-h-[70vh] max-w-7xl px-5 pb-24 pt-12 lg:px-8">
        <nav
          aria-label="Breadcrumb"
          className="mb-10 flex items-center gap-2 text-xs font-medium text-muted"
        >
          <Link className="hover:text-ink" href="/">
            Overview
          </Link>
          <span aria-hidden="true">/</span>
          <span className="text-ink">Interactive demo</span>
        </nav>
        <div className="mb-10 flex flex-wrap items-end justify-between gap-6">
          <div className="max-w-2xl">
            <span className="demo-kicker">
              <span className="demo-kicker-dot" /> TAKE A CLOSER LOOK
            </span>
            <h1 className="mt-4 text-4xl font-semibold tracking-[-.05em] text-ink sm:text-5xl">
              A review you can explore.
            </h1>
            <p className="mt-4 max-w-xl text-base leading-7 text-muted">
              Try a sample résumé and role. Follow each finding back to the original wording.
            </p>
          </div>
          <div className="rounded-xl border border-line bg-surface px-4 py-3 text-xs leading-5 text-muted">
            <strong className="block font-semibold text-ink">Private by design</strong>
            Demo content is synthetic and is not saved.
          </div>
        </div>
        <div className="grid gap-6 lg:grid-cols-[340px_minmax(0,1fr)] lg:items-start">
          <aside className="demo-panel p-6 lg:sticky lg:top-24">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold tracking-tight">Choose an example</h2>
              <span className="demo-step">01 / 02</span>
            </div>
            <p className="mt-2 text-sm leading-6 text-muted">
              Pick a résumé and the role to compare it with.
            </p>
            {samples.loading && !samples.data && !samples.error && (
              <div role="status" className="mt-7 space-y-4" aria-label="Fetching demo examples">
                <div className="h-4 w-24 animate-pulse rounded bg-raised" />
                <div className="h-12 animate-pulse rounded-lg bg-raised" />
                <div className="h-4 w-24 animate-pulse rounded bg-raised" />
                <div className="h-12 animate-pulse rounded-lg bg-raised" />
                <p className="text-xs text-muted">Connecting to the local analysis API…</p>
              </div>
            )}
            {!!samples.error && (
              <div className="mt-6">
                <ErrorState error={samples.error} onRetry={samples.reload} />
                <p className="mt-3 text-xs leading-5 text-muted">
                  The analysis service is unavailable. Try again shortly.
                </p>
              </div>
            )}
            {samples.data && (
              <form onSubmit={run} className="mt-7 space-y-6">
                <div>
                  <label
                    htmlFor="demo-resume"
                    className="mb-2 block text-xs font-semibold uppercase tracking-widest text-muted"
                  >
                    01 — Sample résumé
                  </label>
                  <Select
                    id="demo-resume"
                    required
                    className="demo-select"
                    value={resume}
                    onChange={(value) => {
                      setResume(value);
                      setResult(null);
                    }}
                  >
                    <option value="">Select a résumé</option>
                    {samples.data.resumes.map((r) => (
                      <option key={r.id} value={r.id} data-description={r.description}>
                        {r.title}
                      </option>
                    ))}
                  </Select>
                  <p className="mt-2 min-h-10 text-xs leading-5 text-muted">
                    {samples.data.resumes.find((r) => r.id === resume)?.description ??
                      "Select a document to review its evidence."}
                  </p>
                </div>
                <div>
                  <label
                    htmlFor="demo-job"
                    className="mb-2 block text-xs font-semibold uppercase tracking-widest text-muted"
                  >
                    02 — Target role
                  </label>
                  <Select
                    id="demo-job"
                    required
                    className="demo-select"
                    value={job}
                    onChange={(value) => {
                      setJob(value);
                      setResult(null);
                    }}
                  >
                    <option value="">Select a job description</option>
                    {samples.data.jobs.map((j) => (
                      <option key={j.id} value={j.id} data-description={j.description}>
                        {j.title}
                      </option>
                    ))}
                  </Select>
                  <p className="mt-2 min-h-10 text-xs leading-5 text-muted">
                    {samples.data.jobs.find((j) => j.id === job)?.description ??
                      "Select the requirements to compare against."}
                  </p>
                </div>
                <Button type="submit" className="w-full" busy={busy} disabled={!resume || !job}>
                  {busy ? "Analyzing evidence…" : "Analyze these documents"}{" "}
                  <Icon name="arrowUpRight" size={17} />
                </Button>
                <p className="text-xs leading-5 text-muted">
                  This demo uses a clearly labeled rule-based baseline. Neural models are not
                  represented as active or accurate until they are evaluated and approved.
                </p>
              </form>
            )}
          </aside>
          <section
            aria-label="Analysis results"
            className="demo-panel min-h-[470px] overflow-hidden"
          >
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-6 py-4">
              <div className="flex items-center gap-3">
                <span className="demo-document-icon">
                  <Icon name="document" size={20} />
                </span>
                <div>
                  <p className="text-sm font-semibold">Analysis report</p>
                  <p className="text-xs text-muted">Evidence and interpretation</p>
                </div>
              </div>
              <span className="demo-engine-badge">
                {result ? "Rule-based analysis" : "Waiting for documents"}
              </span>
            </div>
            <div className="p-6 sm:p-8" aria-live="polite">
              {!!error && (
                <div className="mb-5">
                  <ErrorState error={error} />
                </div>
              )}
              {busy && (
                <div role="status" className="space-y-4">
                  <div className="h-7 w-2/5 animate-pulse rounded bg-raised" />
                  <div className="h-24 animate-pulse rounded-xl bg-raised" />
                  <div className="h-24 animate-pulse rounded-xl bg-raised" />
                  <p className="text-sm text-muted">
                    Comparing the selected job requirements against the résumé text…
                  </p>
                </div>
              )}
              {!busy && result && (
                <>
                  <details className="source-reader mb-7">
                    <summary>
                      Inspect the source documents{" "}
                      <span>
                        Résumé &amp; role <Icon name="chevronDown" size={14} />
                      </span>
                    </summary>
                    <div className="source-columns">
                      <div>
                        <h3>Résumé · extracted text</h3>
                        {result.resume.normalized.blocks.map((b) => (
                          <p key={b.id}>
                            <span>{b.line}</span>
                            {b.text}
                          </p>
                        ))}
                      </div>
                      <div>
                        <h3>Job description · source</h3>
                        <pre>{result.job.text}</pre>
                      </div>
                    </div>
                  </details>
                  <div className="mb-7">
                    <p className="text-xs font-semibold uppercase tracking-widest text-muted">
                      Completed comparison
                    </p>
                    <h2 className="mt-2 text-2xl font-semibold tracking-tight">
                      {result.resume.title}
                    </h2>
                    <p className="mt-1 text-sm text-muted">Against {result.job.title}</p>
                  </div>
                  {result.resume.parseability.signals.length > 0 && (
                    <div className="mb-4">
                      <Notice tone="warn">{result.resume.parseability.signals[0]!.message}</Notice>
                    </div>
                  )}
                  <AnalysisResults
                    engine={result.engine}
                    assessments={result.assessments}
                    warnings={result.warnings}
                    matches={result.matches}
                    limitations={result.limitations}
                    recommendations={result.recommendations}
                  />
                </>
              )}
              {!busy && !result && (
                <div className="flex min-h-[360px] flex-col items-center justify-center px-4 text-center">
                  <div className="demo-empty-visual" aria-hidden="true">
                    <Icon name="document" size={30} />
                    <span className="demo-empty-line" />
                    <span className="demo-empty-line short" />
                    <span className="demo-empty-line" />
                  </div>
                  <h2 className="mt-8 text-xl font-semibold tracking-tight">
                    Your evidence report will appear here
                  </h2>
                  <p className="mt-3 max-w-sm text-sm leading-6 text-muted">
                    Choose a résumé and a target role to examine matched evidence, uncertainties and
                    actionable next steps.
                  </p>
                  <div className="mt-7 flex flex-wrap justify-center gap-2">
                    <span className="demo-neutral-tag">Source-linked findings</span>
                    <span className="demo-neutral-tag">Clear limitations</span>
                    <span className="demo-neutral-tag">No invented scores</span>
                  </div>
                </div>
              )}
            </div>
          </section>
        </div>
      </main>
      <SiteFooter />
    </>
  );
}
