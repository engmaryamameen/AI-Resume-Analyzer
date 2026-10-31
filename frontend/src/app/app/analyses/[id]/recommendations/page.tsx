"use client";

import Link from "next/link";
import { Icon } from "@/components/icon";
import { useParams, useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { Diff } from "@/components/diff";
import {
  Badge,
  Button,
  Card,
  ErrorState,
  Loading,
  Notice,
  PageHeader,
  TextArea,
} from "@/components/ui";
import { api, ApiError, newIdempotencyKey } from "@/lib/api";
import { RECOMMENDATION_KIND, friendlyError } from "@/lib/copy";
import { useAsync } from "@/lib/hooks";
import type { Recommendation } from "@/lib/types";

interface Saved {
  before: string;
  after: string;
  versionId: string;
}

export default function Recommendations() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const analysis = useAsync(() => api.analysis(id), [id]);
  const documentId = analysis.data?.resume_document_id ?? null;
  const resume = useAsync(
    () => (documentId ? api.resume(documentId) : Promise.resolve(null)),
    [documentId],
  );

  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState<Record<string, Saved>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [rerunning, setRerunning] = useState(false);
  const [message, setMessage] = useState<{ tone: "good" | "bad"; text: string } | null>(null);
  const rerunKey = useRef(newIdempotencyKey());

  if (analysis.loading || resume.loading) return <Loading />;
  if (analysis.error || !analysis.data)
    return <ErrorState error={analysis.error} onRetry={analysis.reload} />;
  if (resume.error) return <ErrorState error={resume.error} onRetry={resume.reload} />;
  const run = analysis.data;
  const latest = resume.data?.versions.at(-1);
  const current = latest && latest.version_no === run.resume_version_no;
  const blocks = new Map((resume.data?.normalized?.blocks ?? []).map((b) => [b.id, b.text]));

  async function save(rec: Recommendation) {
    const bid = rec.block_id!;
    const before = blocks.get(bid) ?? rec.excerpt ?? "";
    const after = (drafts[bid] ?? before).trim();
    if (!after || after === before)
      return setMessage({ tone: "bad", text: "Change the line first, or leave it as it is." });
    setBusy(bid);
    setMessage(null);
    try {
      const v = await api.correctResume(documentId!, {
        base_version_no: latest!.version_no,
        block_edits: { [bid]: after },
      });
      setSaved((s) => ({ ...s, [bid]: { before, after, versionId: v.id } }));
      setMessage({
        tone: "good",
        text: `Saved as version ${v.version_no}. Run the analysis again to see what changed.`,
      });
      resume.reload();
    } catch (e) {
      const stale = e instanceof ApiError && e.code === "stale_base_version";
      setMessage({
        tone: "bad",
        text: stale
          ? "The résumé was changed somewhere else, so nothing was saved. Reload to start from the latest version."
          : friendlyError(e),
      });
    } finally {
      setBusy(null);
    }
  }

  async function rerun() {
    const newest = Object.values(saved).at(-1)?.versionId ?? latest?.id;
    if (!newest) return;
    setRerunning(true);
    try {
      const next = await api.createAnalysis(newest, run.jd_version_id, rerunKey.current);
      router.push(`/app/analyses/${next.id}`);
    } catch (e) {
      setMessage({ tone: "bad", text: friendlyError(e) });
      setRerunning(false);
    }
  }

  return (
    <>
      <PageHeader title="Suggestions for your résumé">
        Each one points at your own words. If a suggestion is right, change the line yourself using
        details that are true. Nothing is written for you.
      </PageHeader>
      <p className="mb-4">
        <Link href={`/app/analyses/${id}`} className="back-link text-accent underline">
          <Icon name="arrowLeft" size={16} /> Back to the analysis
        </Link>
      </p>
      <div aria-live="polite">
        {message && (
          <div className="mb-4">
            <Notice tone={message.tone}>{message.text}</Notice>
          </div>
        )}
      </div>
      {!current && (
        <div className="mb-4">
          <Notice tone="warn" title="You can't edit from this analysis">
            This analysis was run on an older version of the résumé. Run it again on the latest
            version first.
          </Notice>
        </div>
      )}
      {run.recommendations.length === 0 && <Notice>Nothing to suggest for this analysis.</Notice>}
      <ul className="space-y-4">
        {run.recommendations.map((rec, i) => {
          const bid = rec.block_id;
          const done = bid ? saved[bid] : undefined;
          return (
            <Card as="li" key={`${rec.kind}-${i}`} className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="plain">{RECOMMENDATION_KIND[rec.kind]}</Badge>
                <h2 className="font-medium">{rec.title}</h2>
              </div>
              <p className="text-sm">{rec.detail}</p>
              {rec.fill_in && (
                <p className="rounded-lg border border-dashed border-line px-3 py-2 text-sm">
                  <span className="font-medium">
                    A template for you to fill in with true details:{" "}
                  </span>
                  {rec.fill_in}
                </p>
              )}
              {bid && rec.excerpt && current && !done && (
                <div id={bid} className="space-y-2">
                  <TextArea
                    label="Your line"
                    hint="Edit it in your own words."
                    rows={3}
                    value={drafts[bid] ?? blocks.get(bid) ?? rec.excerpt}
                    onChange={(e) => setDrafts({ ...drafts, [bid]: e.target.value })}
                  />
                  {(drafts[bid] ?? "") !== "" &&
                    (drafts[bid] ?? "") !== (blocks.get(bid) ?? rec.excerpt) && (
                      <div>
                        <p className="text-sm font-medium">What would change</p>
                        <Diff before={blocks.get(bid) ?? rec.excerpt} after={drafts[bid]!} />
                      </div>
                    )}
                  <Button variant="secondary" busy={busy === bid} onClick={() => save(rec)}>
                    Save this line
                  </Button>
                </div>
              )}
              {bid && rec.excerpt && !current && (
                <blockquote className="rounded-lg bg-raised px-3 py-2 text-sm">
                  {rec.excerpt}
                </blockquote>
              )}
              {done && (
                <div>
                  <p className="text-sm font-medium">Saved. Before and after</p>
                  <Diff before={done.before} after={done.after} />
                </div>
              )}
            </Card>
          );
        })}
      </ul>
      {Object.keys(saved).length > 0 && (
        <div className="mt-6">
          <Button onClick={rerun} busy={rerunning}>
            Run the analysis again on the new version
          </Button>
        </div>
      )}
    </>
  );
}
