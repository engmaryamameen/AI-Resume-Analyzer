"use client";

import Link from "next/link";
import { useState } from "react";
import { Badge, ButtonLink, Card, EmptyState, ErrorState, Loading, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/copy";
import { useAsync } from "@/lib/hooks";

const STATUS_TEXT: Record<string, string> = {
  queued: "Waiting to start", running: "Working on it", succeeded: "Done", failed: "Didn't finish", cancelled: "Cancelled",
};

export default function History() {
  const list = useAsync(() => api.analyses(), []);
  const [picked, setPicked] = useState<string[]>([]);

  if (list.loading) return <Loading />;
  if (list.error || !list.data) return <ErrorState error={list.error} onRetry={list.reload} />;
  const items = list.data.items;
  const earlierFirst = items.filter((a) => picked.includes(a.id)).sort((x, y) => x.created_at.localeCompare(y.created_at)).map((a) => a.id);
  const toggle = (id: string) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id].slice(-2)));

  return (
    <>
      <PageHeader title="History" actions={<ButtonLink href="/app/analyses/new">New analysis</ButtonLink>}>
        Every analysis you've run. Tick two finished ones to see what changed between them.
      </PageHeader>
      {items.length === 0 ? (
        <EmptyState title="Nothing here yet" action={<ButtonLink href="/app/analyses/new">Run your first analysis</ButtonLink>}>
          After you analyse a résumé, you can come back here to compare versions or different roles.
        </EmptyState>
      ) : (
        <>
          <ul className="space-y-3">
            {items.map((a) => (
              <Card as="li" key={a.id} className="flex flex-wrap items-center gap-4">
                <input type="checkbox" aria-label={`Select analysis from ${formatDate(a.created_at)} for comparison`}
                  disabled={a.status !== "succeeded"} checked={picked.includes(a.id)} onChange={() => toggle(a.id)} className="h-5 w-5" />
                <div className="grow">
                  <Link href={`/app/analyses/${a.id}`} className="font-medium text-accent underline">Analysis from {formatDate(a.created_at)}</Link>
                  <p className="text-sm text-muted">{a.engine ? (a.engine.mode === "learned" ? "Read by local models" : "Rule-based reading") : "Not read yet"}</p>
                </div>
                {a.staleness.is_stale && <Badge tone="warn">Out of date</Badge>}
                <Badge tone={a.status === "succeeded" ? "good" : a.status === "failed" ? "bad" : "info"}>{STATUS_TEXT[a.status] ?? a.status}</Badge>
              </Card>
            ))}
          </ul>
          <div className="mt-6">
            <ButtonLink href={picked.length === 2 ? `/app/analyses/compare?base=${earlierFirst[0]}&target=${earlierFirst[1]}` : "#"} variant="secondary"
              className={picked.length === 2 ? "" : "pointer-events-none opacity-50"}>
              {picked.length === 2 ? "Compare the two" : "Pick two to compare"}
            </ButtonLink>
          </div>
        </>
      )}
    </>
  );
}
