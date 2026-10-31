"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import {
  Badge,
  Button,
  ButtonLink,
  Card,
  EmptyState,
  ErrorState,
  Loading,
  PageHeader,
  Pagination,
} from "@/components/ui";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/copy";
import { useAsync } from "@/lib/hooks";
import type { Analysis } from "@/lib/types";

const STATUS_TEXT: Record<string, string> = {
  queued: "Waiting to start",
  running: "Working on it",
  succeeded: "Done",
  failed: "Didn't finish",
  cancelled: "Cancelled",
};

export default function History() {
  const router = useRouter();
  const [offset, setOffset] = useState(0);
  const list = useAsync(() => api.analyses(offset), [offset]);
  const [picked, setPicked] = useState<Analysis[]>([]);

  const header = (
    <PageHeader
      title="Review history"
      actions={<ButtonLink href="/app/analyses/new">New analysis</ButtonLink>}
    >
      Every analysis you&apos;ve run. Tick two finished ones to see what changed between them.
    </PageHeader>
  );
  if (list.loading)
    return (
      <>
        {header}
        <Loading label="Loading your review history…" />
      </>
    );
  if (list.error || !list.data)
    return (
      <>
        {header}
        <ErrorState error={list.error} onRetry={list.reload} />
      </>
    );
  const items = list.data.items;
  const earlierFirst = [...picked]
    .sort((x, y) => x.created_at.localeCompare(y.created_at))
    .map((a) => a.id);
  const toggle = (analysis: Analysis) =>
    setPicked((p) =>
      p.some((x) => x.id === analysis.id)
        ? p.filter((x) => x.id !== analysis.id)
        : [...p, analysis].slice(-2),
    );

  return (
    <>
      {header}
      {items.length === 0 ? (
        <EmptyState
          title="Nothing here yet"
          action={<ButtonLink href="/app/analyses/new">Run your first analysis</ButtonLink>}
        >
          After you analyze a résumé, you can come back here to compare versions or different roles.
        </EmptyState>
      ) : (
        <>
          <ul className="space-y-3">
            {items.map((a) => (
              <Card as="li" key={a.id} className="flex flex-wrap items-center gap-4">
                <input
                  type="checkbox"
                  aria-label={`Select analysis from ${formatDateTime(a.created_at)} for comparison`}
                  disabled={a.status !== "succeeded"}
                  checked={picked.some((x) => x.id === a.id)}
                  onChange={() => toggle(a)}
                  className="h-5 w-5"
                />
                <div className="grow">
                  <Link
                    href={`/app/analyses/${a.id}`}
                    className="font-medium text-accent underline"
                  >
                    Analysis from {formatDateTime(a.created_at)}
                  </Link>
                  <p className="text-xs text-muted">
                    Résumé v{a.resume_version_no ?? "—"} · Review {a.id.slice(0, 8)}
                  </p>
                  <p className="text-sm text-muted">
                    {a.engine
                      ? a.engine.mode !== "rules"
                        ? "Read by local models"
                        : "Rule-based reading"
                      : "Not read yet"}
                  </p>
                </div>
                {a.staleness.is_stale && <Badge tone="warn">Out of date</Badge>}
                <Badge
                  tone={a.status === "succeeded" ? "good" : a.status === "failed" ? "bad" : "info"}
                >
                  {STATUS_TEXT[a.status] ?? a.status}
                </Badge>
              </Card>
            ))}
          </ul>
          <div className="mt-6">
            {picked.length > 0 && (
              <p className="mb-3 text-xs text-muted">
                {picked.length} selected for comparison, including selections on other pages.
              </p>
            )}
            <Button
              variant="secondary"
              disabled={picked.length !== 2}
              onClick={() =>
                router.push(
                  `/app/analyses/compare?base=${earlierFirst[0]}&target=${earlierFirst[1]}`,
                )
              }
            >
              {picked.length === 2 ? "Compare the two" : "Pick two to compare"}
            </Button>
          </div>
        </>
      )}
      {list.data && <Pagination offset={offset} total={list.data.total} onChange={setOffset} />}
    </>
  );
}
