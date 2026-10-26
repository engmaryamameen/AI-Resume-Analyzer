"use client";

import { useState } from "react";
import { AnalysisResults } from "@/components/analysis-view";
import { ModelStatusPanel } from "@/components/model-status";
import { SiteFooter, SiteHeader } from "@/components/site-header";
import { Button, Card, ErrorState, Loading, Notice, PageHeader } from "@/components/ui";
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

  async function run(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
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
      <main id="main" className="mx-auto max-w-6xl px-4 py-10">
        <PageHeader title="Try it with sample documents">Pick a made-up résumé and a made-up job. The demo uses the simple rule-based reader, and the result says so.</PageHeader>
        {samples.loading && <Loading />}
        {!!samples.error && <ErrorState error={samples.error} onRetry={samples.reload} />}
        {samples.data && (
          <Card className="mb-8">
            <form onSubmit={run} className="grid gap-4 md:grid-cols-3 md:items-end">
              <div>
                <label htmlFor="demo-resume" className="block text-sm font-medium">Résumé</label>
                <select id="demo-resume" required value={resume} onChange={(e) => setResume(e.target.value)} className="mt-1 min-h-[44px] w-full rounded-lg border border-line bg-surface px-3">
                  <option value="" disabled>Choose one…</option>
                  {samples.data.resumes.map((r) => <option key={r.id} value={r.id}>{r.title}</option>)}
                </select>
                <p className="mt-1 text-sm text-muted">{samples.data.resumes.find((r) => r.id === resume)?.description}</p>
              </div>
              <div>
                <label htmlFor="demo-job" className="block text-sm font-medium">Job description</label>
                <select id="demo-job" required value={job} onChange={(e) => setJob(e.target.value)} className="mt-1 min-h-[44px] w-full rounded-lg border border-line bg-surface px-3">
                  <option value="" disabled>Choose one…</option>
                  {samples.data.jobs.map((j) => <option key={j.id} value={j.id}>{j.title}</option>)}
                </select>
                <p className="mt-1 text-sm text-muted">{samples.data.jobs.find((j) => j.id === job)?.description}</p>
              </div>
              <Button type="submit" busy={busy} disabled={!resume || !job}>Analyse</Button>
            </form>
            <p className="mt-3 text-sm text-muted">{samples.data.notice}</p>
          </Card>
        )}
        <div aria-live="polite">
          {!!error && <ErrorState error={error} />}
          {result && (
            <>
              <h2 className="mb-1 font-serif text-2xl">{result.resume.title} against {result.job.title}</h2>
              {result.resume.parseability.signals.length > 0 && <div className="mb-4"><Notice tone="warn">{result.resume.parseability.signals[0]!.message}</Notice></div>}
              <AnalysisResults engine={result.engine} assessments={result.assessments} warnings={result.warnings}
                matches={result.matches} limitations={result.limitations} recommendations={result.recommendations} />
            </>
          )}
        </div>
        {!result && <div className="mt-8"><ModelStatusPanel /></div>}
      </main>
      <SiteFooter />
    </>
  );
}
