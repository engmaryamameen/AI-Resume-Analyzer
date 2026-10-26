"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useRef, useState } from "react";
import { ModelStatusPanel } from "@/components/model-status";
import { Button, Card, EmptyState, ErrorState, Loading, Notice, PageHeader } from "@/components/ui";
import { api, newIdempotencyKey } from "@/lib/api";
import { friendlyError } from "@/lib/copy";
import { useAsync } from "@/lib/hooks";

function NewAnalysis() {
  const router = useRouter();
  const params = useSearchParams();
  const resumes = useAsync(() => api.resumes(), []);
  const jobs = useAsync(() => api.jobs(), []);
  const [resumeVersion, setResumeVersion] = useState(params.get("resume") ?? "");
  const [jobVersion, setJobVersion] = useState(params.get("job") ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const key = useRef(newIdempotencyKey()); // double-clicks or retries resolve to one analysis

  if (resumes.loading || jobs.loading) return <Loading />;
  const failed = resumes.error || jobs.error;
  if (failed) return <ErrorState error={failed} onRetry={() => { resumes.reload(); jobs.reload(); }} />;
  const ready = resumes.data!.items.filter((r) => r.latest_version.status === "ready");
  if (ready.length === 0 || jobs.data!.items.length === 0) {
    return (
      <EmptyState title="You'll need one of each first"
        action={<div className="flex gap-3"><Link className="text-accent underline" href="/app/resumes">Add a résumé</Link><Link className="text-accent underline" href="/app/jobs">Add a job</Link></div>}>
        An analysis compares a résumé that has been read successfully with a job description.
      </EmptyState>
    );
  }

  async function start(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const run = await api.createAnalysis(resumeVersion, jobVersion, key.current);
      router.push(`/app/analyses/${run.id}`);
    } catch (err) {
      setError(friendlyError(err));
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title="New analysis">Pick the résumé and the job to compare.</PageHeader>
      <Card>
        <form onSubmit={start} className="space-y-5">
          <div>
            <label htmlFor="resume" className="block font-medium">Résumé</label>
            <select id="resume" required value={resumeVersion} onChange={(e) => setResumeVersion(e.target.value)} className="mt-1 min-h-[44px] w-full rounded-lg border border-line bg-surface px-3">
              <option value="">Choose one…</option>
              {ready.map((r) => <option key={r.id} value={r.latest_version.id}>{r.title} (latest version, {r.latest_version.version_no})</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="job" className="block font-medium">Job description</label>
            <select id="job" required value={jobVersion} onChange={(e) => setJobVersion(e.target.value)} className="mt-1 min-h-[44px] w-full rounded-lg border border-line bg-surface px-3">
              <option value="">Choose one…</option>
              {jobs.data!.items.map((j) => <option key={j.id} value={j.latest_version.id}>{j.title} (version {j.latest_version.version_no})</option>)}
            </select>
          </div>
          {error && <Notice tone="bad">{error}</Notice>}
          <Button type="submit" busy={busy}>Start analysis</Button>
        </form>
      </Card>
      <div className="mt-8"><ModelStatusPanel /></div>
    </>
  );
}

export default function Page() {
  return <Suspense fallback={<Loading />}><NewAnalysis /></Suspense>;
}
