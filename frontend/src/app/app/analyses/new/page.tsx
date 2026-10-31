"use client";

import { Select } from "@/components/select";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useRef, useState } from "react";
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  Loading,
  Notice,
  PageHeader,
  Pagination,
} from "@/components/ui";
import { api, newIdempotencyKey } from "@/lib/api";
import { friendlyError } from "@/lib/copy";
import { useAsync } from "@/lib/hooks";

function NewAnalysis() {
  const router = useRouter();
  const params = useSearchParams();
  const [resumeOffset, setResumeOffset] = useState(0);
  const [jobOffset, setJobOffset] = useState(0);
  const resumes = useAsync(() => api.resumes(resumeOffset), [resumeOffset]);
  const jobs = useAsync(() => api.jobs(jobOffset), [jobOffset]);
  const [resumeLabel, setResumeLabel] = useState("");
  const [jobLabel, setJobLabel] = useState("");
  const [resumeVersion, setResumeVersion] = useState(params.get("resume") ?? "");
  const [jobVersion, setJobVersion] = useState(params.get("job") ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const key = useRef<{ selection: string; value: string } | null>(null); // Same payload retries share a key; a changed selection gets a new key.

  if (resumes.loading || jobs.loading) return <Loading />;
  const failed = resumes.error || jobs.error;
  if (failed)
    return (
      <ErrorState
        error={failed}
        onRetry={() => {
          resumes.reload();
          jobs.reload();
        }}
      />
    );
  const ready = resumes.data!.items.filter((r) => r.latest_version.status === "ready");
  if (resumes.data!.total === 0 || jobs.data!.total === 0) {
    return (
      <>
        <PageHeader title="New analysis">
          Choose a résumé and a target role to review together.
        </PageHeader>
        <EmptyState
          title="You'll need one of each first"
          action={
            <div className="flex gap-3">
              <Link className="text-accent underline" href="/app/resumes">
                Add a résumé
              </Link>
              <Link className="text-accent underline" href="/app/jobs">
                Add a job
              </Link>
            </div>
          }
        >
          An analysis compares a résumé that has been read successfully with a job description.
        </EmptyState>
      </>
    );
  }

  async function start(e: React.FormEvent) {
    e.preventDefault();
    if (busy || !resumeVersion || !jobVersion) return;
    const selection = JSON.stringify([resumeVersion, jobVersion]);
    if (key.current?.selection !== selection)
      key.current = { selection, value: newIdempotencyKey() };
    setBusy(true);
    setError(null);
    try {
      const run = await api.createAnalysis(resumeVersion, jobVersion, key.current.value);
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
          <div aria-label="Résumé choices">
            <label htmlFor="resume" className="block font-medium">
              Résumé
            </label>
            <Select
              id="resume"
              required
              value={resumeVersion}
              disabled={busy}
              onChange={(value) => {
                setResumeVersion(value);
                const r = ready.find((item) => item.latest_version.id === value);
                setResumeLabel(r ? `${r.title} (version ${r.latest_version.version_no})` : "");
              }}
              className="mt-1 min-h-[44px] w-full rounded-lg border border-line bg-surface px-3"
            >
              <option value="">Choose one…</option>
              {resumeVersion && !ready.some((r) => r.latest_version.id === resumeVersion) && (
                <option value={resumeVersion}>
                  {resumeLabel || "Selected résumé version from document review"}
                </option>
              )}
              {ready.map((r) => (
                <option key={r.id} value={r.latest_version.id}>
                  {r.title} (latest version, {r.latest_version.version_no})
                </option>
              ))}
            </Select>
            {ready.length === 0 && (
              <p className="mt-2 text-sm text-muted">
                No ready résumés on this page. Browse another page or wait for extraction to finish.
              </p>
            )}
            <Pagination
              offset={resumeOffset}
              total={resumes.data!.total}
              onChange={setResumeOffset}
            />
          </div>
          <div aria-label="Target-role choices">
            <label htmlFor="job" className="block font-medium">
              Job description
            </label>
            <Select
              id="job"
              required
              value={jobVersion}
              disabled={busy}
              onChange={(value) => {
                setJobVersion(value);
                const j = jobs.data!.items.find((item) => item.latest_version.id === value);
                setJobLabel(j ? `${j.title} (version ${j.latest_version.version_no})` : "");
              }}
              className="mt-1 min-h-[44px] w-full rounded-lg border border-line bg-surface px-3"
            >
              <option value="">Choose one…</option>
              {jobVersion && !jobs.data!.items.some((j) => j.latest_version.id === jobVersion) && (
                <option value={jobVersion}>
                  {jobLabel || "Selected target-role version from role review"}
                </option>
              )}
              {jobs.data!.items.map((j) => (
                <option key={j.id} value={j.latest_version.id}>
                  {j.title} (version {j.latest_version.version_no})
                </option>
              ))}
            </Select>
            <Pagination offset={jobOffset} total={jobs.data!.total} onChange={setJobOffset} />
          </div>
          {error && <Notice tone="bad">{error}</Notice>}
          <Button type="submit" busy={busy} disabled={!resumeVersion || !jobVersion}>
            Start analysis
          </Button>
        </form>
      </Card>
    </>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<Loading />}>
      <NewAnalysis />
    </Suspense>
  );
}
