"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { AnalysisResults } from "@/features/analyses/components/analysis-report";
import { Button, ButtonLink, ErrorState, Loading, Notice, PageHeader } from "@/components/ui";
import { analysesApi } from "@/features/analyses/api";
import { STALE_REASON, analysisFailure, formatDateTime, friendlyError } from "@/lib/copy";
import { useQuery, usePolling } from "@/lib/hooks";
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
  const a = useQuery(["analysis", id], (signal) => analysesApi.analysis(id, signal));
  const [cancelError, setCancelError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const active = a.data?.status === "queued" || a.data?.status === "running";
  usePolling(active, a.reload);

  if (a.loading)
    return (
      <>
        <PageHeader title="Analysis" />
        <Loading />
      </>
    );
  if (a.error || !a.data)
    return (
      <>
        <PageHeader title="Analysis" />
        <ErrorState error={a.error} onRetry={a.reload} />
      </>
    );
  const run = a.data;

  async function cancel() {
    setCancelling(true);
    setCancelError(null);
    try {
      await analysesApi.cancelAnalysis(id);
      a.reload();
    } catch (e) {
      setCancelError(friendlyError(e));
    } finally {
      setCancelling(false);
    }
  }

  return (
    <>
      <PageHeader
        title={`Analysis from ${formatDateTime(run.created_at)}`}
        actions={
          run.status === "succeeded" ? (
            <>
              <ButtonLink href={`/app/analyses/${id}/recommendations`}>Edit résumé</ButtonLink>
              <div className="flex min-h-[44px] flex-wrap items-center gap-4 px-2 text-xs">
                <span className="text-muted">Export</span>
                {(["md", "csv", "json"] as const).map((format) => (
                  <a
                    key={format}
                    href={analysesApi.reportUrl(id, format)}
                    download
                    aria-label={`Download ${format === "md" ? "Markdown" : format.toUpperCase()} report`}
                    className="inline-flex min-h-[44px] items-center text-accent underline decoration-line underline-offset-4 hover:decoration-accent"
                  >
                    {format === "md" ? "Markdown" : format.toUpperCase()}
                  </a>
                ))}
              </div>
            </>
          ) : undefined
        }
      >
        {run.resume_version_no ? `Résumé version ${run.resume_version_no}. ` : ""}Each requirement
        below shows the lines of the résumé it rests on.
      </PageHeader>

      {run.staleness.is_stale && (
        <div className="mb-6">
          <Notice tone="warn" title="This analysis is out of date">
            <ul className="list-disc pl-5">
              {run.staleness.reasons.map((r) => (
                <li key={r}>{STALE_REASON[r] ?? r}</li>
              ))}
            </ul>
            <p className="mt-2">
              <Link href={`/app/analyses/new?${rerunQuery(run)}`} className="text-accent underline">
                Run it again
              </Link>{" "}
              to see current results.
            </p>
          </Notice>
        </div>
      )}

      <div aria-live="polite">
        {active && (
          <div>
            <Loading
              label={
                run.status === "queued"
                  ? "Waiting for the worker to pick this up…"
                  : "Reading the résumé against the job…"
              }
            />
            <Button variant="secondary" busy={cancelling} onClick={cancel}>
              Cancel
            </Button>
            {cancelError && (
              <div className="mt-3">
                <Notice tone="bad">{cancelError}</Notice>
              </div>
            )}
          </div>
        )}
        {run.status === "failed" && (
          <Notice tone="bad" title="This analysis didn't finish">
            {analysisFailure(run.error_code)} Nothing partial was saved.
          </Notice>
        )}
        {run.status === "cancelled" && <Notice>You cancelled this analysis.</Notice>}
      </div>
      {run.status === "succeeded" && (
        <AnalysisResults
          review={run.review}
          engine={run.engine}
          assessments={run.assessments}
          warnings={run.warnings}
          matches={run.matches}
          limitations={run.limitations}
          recommendations={run.recommendations}
          recommendationsHref={`/app/analyses/${id}/recommendations`}
        />
      )}
    </>
  );
}
