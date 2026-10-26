"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { AnalysisResults } from "@/components/analysis-view";
import { Button, ButtonLink, ErrorState, Loading, Notice, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { STALE_REASON, analysisFailure, formatDate, friendlyError } from "@/lib/copy";
import { useAsync, usePolling } from "@/lib/hooks";
import type { Analysis } from "@/lib/types";

// A re-run starts from the newest version of both inputs.
function rerunQuery(run: Analysis): string {
  const query = new URLSearchParams();
  if (run.latest_resume_version_id) query.set("resume", run.latest_resume_version_id);
  if (run.latest_jd_version_id) query.set("job", run.latest_jd_version_id);
  return query.toString();
}

export default function AnalysisPage() {
  const { id } = useParams<{ id: string }>();
  const a = useAsync(() => api.analysis(id), [id]);
  const [cancelError, setCancelError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const active = a.data?.status === "queued" || a.data?.status === "running";
  usePolling(active, a.reload);

  const stale = a.data?.staleness.is_stale ?? false;

  if (a.loading) return <Loading />;
  if (a.error || !a.data) return <ErrorState error={a.error} onRetry={a.reload} />;
  const run = a.data;

  async function cancel() {
    setCancelling(true);
    setCancelError(null);
    try { await api.cancelAnalysis(id); a.reload(); } catch (e) { setCancelError(friendlyError(e)); } finally { setCancelling(false); }
  }

  return (
    <>
      <PageHeader title={`Analysis from ${formatDate(run.created_at)}`}
        actions={run.status === "succeeded" ? (
          <>
            <ButtonLink href={`/app/analyses/${id}/recommendations`}>Suggestions</ButtonLink>
            {(["md", "csv", "json"] as const).map((f) => (
              <a key={f} href={api.reportUrl(id, f)} download className="inline-flex min-h-[44px] items-center rounded-lg border border-line bg-surface px-4 text-sm hover:bg-raised">
                Download {f === "md" ? "Markdown" : f.toUpperCase()}
              </a>
            ))}
          </>) : undefined}>
        {run.resume_version_no ? `Résumé version ${run.resume_version_no}. ` : ""}Each requirement below shows the lines of the résumé it rests on.
      </PageHeader>

      {run.staleness.is_stale && (
        <div className="mb-6"><Notice tone="warn" title="This analysis is out of date">
          <ul className="list-disc pl-5">{run.staleness.reasons.map((r) => <li key={r}>{STALE_REASON[r] ?? r}</li>)}</ul>
          <p className="mt-2"><Link href={`/app/analyses/new?${rerunQuery(run)}`} className="text-accent underline">Run it again</Link> to see current results.</p>
        </Notice></div>
      )}

      <div aria-live="polite">
        {active && (
          <div>
            <Loading label={run.status === "queued" ? "Waiting for the worker to pick this up…" : "Reading the résumé against the job…"} />
            <Button variant="secondary" busy={cancelling} onClick={cancel}>Cancel</Button>
            {cancelError && <div className="mt-3"><Notice tone="bad">{cancelError}</Notice></div>}
          </div>
        )}
        {run.status === "failed" && <Notice tone="bad" title="This analysis didn't finish">{analysisFailure(run.error_code)} Nothing partial was saved.</Notice>}
        {run.status === "cancelled" && <Notice>You cancelled this analysis.</Notice>}
      </div>
      {run.status === "succeeded" && (
        <AnalysisResults engine={run.engine} assessments={run.assessments} warnings={run.warnings} matches={run.matches}
          limitations={run.limitations} recommendations={run.recommendations} recommendationsHref={`/app/analyses/${id}/recommendations`} />
      )}
    </>
  );
}
