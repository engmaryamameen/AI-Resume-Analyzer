"use client";

import Link from "next/link";
import { ModelStatusPanel } from "@/components/model-status";
import { ButtonLink, Card, EmptyState, ErrorState, Loading, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/copy";
import { useAsync } from "@/lib/hooks";

export default function Overview() {
  const resumes = useAsync(() => api.resumes(), []);
  const jobs = useAsync(() => api.jobs(), []);
  const runs = useAsync(() => api.analyses(), []);

  if (resumes.loading || jobs.loading || runs.loading) return <Loading />;
  const error = resumes.error || jobs.error || runs.error;
  if (error) return <ErrorState error={error} onRetry={() => { resumes.reload(); jobs.reload(); runs.reload(); }} />;

  const nothingYet = resumes.data!.total === 0 && jobs.data!.total === 0;
  return (
    <>
      <PageHeader title="Your workspace" actions={<ButtonLink href="/app/analyses/new">Start an analysis</ButtonLink>}>
        Add a résumé and a job description, then compare them.
      </PageHeader>
      {nothingYet ? (
        <EmptyState title="Let's start with a résumé" action={<ButtonLink href="/app/resumes">Upload a résumé</ButtonLink>}>
          Upload a PDF or Word file. You'll get to check what we read from it before anything is analysed.
        </EmptyState>
      ) : (
        <div className="grid gap-4 md:grid-cols-3">
          <Card as="div"><p className="font-serif text-4xl">{resumes.data!.total}</p><p className="text-muted">résumés</p><Link href="/app/resumes" className="text-sm text-accent underline">Manage</Link></Card>
          <Card as="div"><p className="font-serif text-4xl">{jobs.data!.total}</p><p className="text-muted">job descriptions</p><Link href="/app/jobs" className="text-sm text-accent underline">Manage</Link></Card>
          <Card as="div"><p className="font-serif text-4xl">{runs.data!.total}</p><p className="text-muted">analyses</p><Link href="/app/analyses" className="text-sm text-accent underline">See history</Link></Card>
        </div>
      )}
      {runs.data!.items.length > 0 && (
        <section className="mt-10" aria-labelledby="recent">
          <h2 id="recent" className="font-serif text-2xl">Most recent</h2>
          <ul className="mt-3 divide-y divide-line rounded-xl border border-line bg-surface">
            {runs.data!.items.slice(0, 4).map((a) => (
              <li key={a.id}><Link href={`/app/analyses/${a.id}`} className="flex items-center justify-between gap-3 px-4 py-3 hover:bg-raised">
                <span>Analysis from {formatDate(a.created_at)}</span><span className="text-sm text-muted">{a.status}{a.staleness.is_stale ? " · out of date" : ""}</span>
              </Link></li>
            ))}
          </ul>
        </section>
      )}
      <div className="mt-10"><ModelStatusPanel /></div>
    </>
  );
}
