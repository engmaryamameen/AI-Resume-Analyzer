"use client";

import Link from "next/link";
import { Icon, type IconName } from "@/components/icon";
import { Badge, ButtonLink, ErrorState, Loading, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/copy";
import { useAsync } from "@/lib/hooks";

export default function Overview() {
  const resumes = useAsync(() => api.resumes(), []);
  const jobs = useAsync(() => api.jobs(), []);
  const runs = useAsync(() => api.analyses(), []);
  if (resumes.loading || jobs.loading || runs.loading) return <Loading />;
  const error = resumes.error || jobs.error || runs.error;
  if (error)
    return (
      <ErrorState
        error={error}
        onRetry={() => {
          resumes.reload();
          jobs.reload();
          runs.reload();
        }}
      />
    );
  const steps = [
    {
      name: "Add your résumé",
      detail: "PDF or DOCX, up to 5 MB. Review the extracted text.",
      href: "/app/resumes",
      done: resumes.data!.items.some((r) => r.latest_version.status === "ready"),
      icon: "document",
    },
    {
      name: "Bring a target role",
      detail: "Paste a job description and refine its requirements.",
      href: "/app/jobs",
      done: jobs.data!.total > 0,
      icon: "briefcase",
    },
    {
      name: "Follow the evidence",
      detail: "Compare the wording. Find your next useful edit.",
      href: "/app/analyses/new",
      done: runs.data!.items.some((r) => r.status === "succeeded"),
      icon: "search",
    },
  ] satisfies { name: string; detail: string; href: string; done: boolean; icon: IconName }[];
  const stats = [
    {
      label: "Résumé library",
      value: resumes.data!.total,
      href: "/app/resumes",
      icon: "document",
      note: "Your documents & versions",
    },
    {
      label: "Target roles",
      value: jobs.data!.total,
      href: "/app/jobs",
      icon: "briefcase",
      note: "Requirements worth reviewing",
    },
    {
      label: "Analysis history",
      value: runs.data!.total,
      href: "/app/analyses",
      icon: "history",
      note: "A record of every comparison",
    },
  ] satisfies { label: string; value: number; href: string; icon: IconName; note: string }[];
  return (
    <div className="workspace-overview">
      <PageHeader
        title="Your next move, in focus."
        actions={
          <ButtonLink href="/app/analyses/new">
            <Icon name="plus" size={16} /> New analysis
          </ButtonLink>
        }
      >
        Your documents, target roles, and reviews. All in one place.
      </PageHeader>
      <div className="workspace-stats">
        {stats.map((s) => (
          <Link className="workspace-stat" key={s.href} href={s.href}>
            <div className="stat-top">
              <span>{s.label}</span>
              <Icon name={s.icon} size={18} />
            </div>
            <strong>{s.value.toString().padStart(2, "0")}</strong>
            <div className="stat-bottom">
              <span>{s.note}</span>
              <Icon name="arrow" size={16} />
            </div>
          </Link>
        ))}
      </div>
      {steps.some((s) => !s.done) && (
        <section className="workspace-guide" aria-labelledby="guide">
          <div className="guide-intro">
            <span className="micro-label">YOUR NEXT CHAPTER</span>
            <h2 id="guide">
              From document
              <br />
              to direction.
            </h2>
            <p>Three small steps toward a résumé that tells your story clearly.</p>
            <span className="guide-progress">
              {steps.filter((s) => s.done).length} of 3 steps completed
            </span>
          </div>
          <ol className="guide-steps">
            {steps.map((s, i) => (
              <li key={s.href}>
                <Link href={s.href}>
                  <span className={`guide-step-icon ${s.done ? "complete" : ""}`}>
                    <Icon name={s.done ? "check" : s.icon} />
                  </span>
                  <div>
                    <span className="micro-label">
                      0{i + 1} {s.done ? " / COMPLETE" : " / NEXT STEP"}
                    </span>
                    <h3>{s.name}</h3>
                    <p>{s.detail}</p>
                  </div>
                  <Icon name="arrow" size={18} />
                </Link>
              </li>
            ))}
          </ol>
        </section>
      )}
      <section className="mt-10" aria-labelledby="recent">
        <div className="section-heading">
          <div>
            <span className="micro-label">THE PAPER TRAIL</span>
            <h2 id="recent">Recent analyses</h2>
          </div>
          <Link href="/app/analyses">
            View all <Icon name="arrow" size={15} />
          </Link>
        </div>
        {runs.data!.items.length ? (
          <ul className="recent-runs">
            {runs.data!.items.slice(0, 5).map((a) => (
              <li key={a.id}>
                <Link href={`/app/analyses/${a.id}`}>
                  <span className="recent-run-icon">
                    <Icon name="document" />
                  </span>
                  <div>
                    <strong>
                      Résumé comparison <span className="recent-review-id">{a.id.slice(0, 8)}</span>
                    </strong>
                    <p>
                      {formatDateTime(a.created_at)} · Version {a.resume_version_no ?? "—"}
                    </p>
                  </div>
                  <Badge
                    tone={
                      a.status === "succeeded" ? "good" : a.status === "failed" ? "bad" : "plain"
                    }
                  >
                    {a.staleness.is_stale
                      ? "Source updated"
                      : a.status === "succeeded"
                        ? "Ready to review"
                        : a.status}
                  </Badge>
                  <Icon name="arrow" size={17} />
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <div className="activity-empty">
            <Icon name="history" size={28} />
            <div>
              <h3>A fresh start.</h3>
              <p>
                Your comparisons will appear here, with the exact document versions that produced
                them.
              </p>
            </div>
            <ButtonLink href="/demo" variant="secondary">
              See an example <Icon name="arrow" size={15} />
            </ButtonLink>
          </div>
        )}
      </section>
    </div>
  );
}
