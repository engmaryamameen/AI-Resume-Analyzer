"use client";

import Link from "next/link";
import { Badge, Card, Notice } from "./ui";
import {
  CATEGORY_LABEL, ENGINE_COPY, EVIDENCE_LABEL, ORIGIN_LABEL, PROBABILITY_EXPLANATION, RECOMMENDATION_KIND, ROLE_LABEL,
  SECTION_LABEL, STATUS, STATUS_ORDER, percent,
} from "@/lib/copy";
import type { Assessment, EngineInfo, Evidence, Match, MatchStatus, Recommendation, Signal } from "@/lib/types";

export function StatusBadge({ status }: { status: MatchStatus }) {
  const s = STATUS[status];
  return <Badge tone={s.tone}><span aria-hidden>{s.icon}</span> {s.label}</Badge>;
}

/** Shown only when the server sent a calibrated probability. Never used for raw similarity. */
export function Probability({ value }: { value: number | null }) {
  if (value === null || value === undefined) return null;
  return (
    <details className="text-sm">
      <summary className="cursor-pointer text-muted">
        Estimated, calibrated: about {percent(value)} likely to be right <span className="underline">What does this mean?</span>
      </summary>
      <p className="mt-1 max-w-prose text-muted">{PROBABILITY_EXPLANATION}</p>
    </details>
  );
}

export function EnginePanel({ engine }: { engine: EngineInfo | null }) {
  if (!engine) return null;
  const learned = engine.mode === "learned";
  return (
    <section aria-labelledby="engine-heading" className="rounded-xl border border-line bg-surface p-5">
      <div className="flex flex-wrap items-center gap-2">
        <h2 id="engine-heading" className="font-serif text-xl">How this was read</h2>
        <Badge tone={learned ? "info" : "plain"}>{learned ? "Local models" : "Rule-based reading"}</Badge>
        {learned && <Badge tone={engine.calibrated ? "good" : "plain"}>{engine.calibrated ? "Calibrated estimates" : "No probability estimates"}</Badge>}
      </div>
      <p className="mt-2 max-w-prose text-sm text-muted">{ENGINE_COPY[engine.mode]}</p>
      {engine.notes.length > 0 && (
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">{engine.notes.map((n) => <li key={n}>{n}</li>)}</ul>
      )}
      {learned && engine.models.length > 0 && (
        <table className="mt-3 w-full text-left text-sm">
          <caption className="sr-only">Models used for this analysis</caption>
          <thead><tr className="text-muted"><th scope="col" className="pr-3 font-medium">Role</th><th scope="col" className="pr-3 font-medium">Model</th>
            <th scope="col" className="pr-3 font-medium">Revision</th><th scope="col" className="font-medium">Licence</th></tr></thead>
          <tbody>
            {engine.models.map((m) => (
              <tr key={m.id} className="align-top">
                <th scope="row" className="pr-3 font-medium capitalize">{m.id}</th>
                <td className="pr-3">{m.base_model}<br /><span className="text-muted">{ORIGIN_LABEL[m.origin]}</span></td>
                <td className="pr-3 font-mono text-xs">{m.revision.slice(0, 12)}</td>
                <td>{m.license}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function Highlighted({ text, ranges }: { text: string; ranges: [number, number][] }) {
  const sorted = [...ranges].filter(([a, b]) => a >= 0 && b > a && b <= text.length).sort((x, y) => x[0] - y[0]);
  const parts: React.ReactNode[] = [];
  let at = 0;
  sorted.forEach(([a, b], i) => {
    if (a < at) return;
    if (a > at) parts.push(text.slice(at, a));
    parts.push(<mark key={i} className="rounded bg-warn/20 px-0.5 text-ink">{text.slice(a, b)}</mark>);
    at = b;
  });
  parts.push(text.slice(at));
  return <>{parts}</>;
}

export function EvidenceCard({ evidence: e }: { evidence: Evidence }) {
  return (
    <figure className="rounded-lg bg-raised px-3 py-2">
      <blockquote className="text-sm"><Highlighted text={e.excerpt} ranges={e.highlights} /></blockquote>
      <figcaption className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
        {e.derived ? <span>Worked out from your dates, not quoted</span> : (
          <>
            {e.section_kind && <span>{SECTION_LABEL[e.section_kind] ?? e.section_kind}</span>}
            {e.label && <span>{EVIDENCE_LABEL[e.label]}</span>}
            {e.roles.length > 0 && <span>{[...new Set(e.roles)].map((r) => ROLE_LABEL[r]).join(", ")}</span>}
          </>
        )}
        {typeof e.retrieval_score === "number" && (
          <span title="Used only to order passages. It is not a probability.">match order value {e.retrieval_score.toFixed(2)}</span>
        )}
      </figcaption>
    </figure>
  );
}

export function RequirementCard({ match }: { match: Match }) {
  const r = match.requirement;
  return (
    <Card as="li" className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="font-medium">{r.text}</h3>
        <StatusBadge status={match.status} />
        {match.conflict && <Badge tone="warn">Conflicting passages</Badge>}
      </div>
      <p className="flex flex-wrap gap-2 text-xs text-muted">
        <span>{r.kind === "required" ? "Must-have" : "Nice-to-have"}</span>
        <span>{CATEGORY_LABEL[r.category] ?? r.category}</span>
        {r.min_years !== null && <span>{r.min_years}+ years</span>}
        {r.origin === "inferred" && <span>inferred from another requirement</span>}
      </p>
      {match.explanation && <p className="text-sm">{match.explanation}</p>}
      {match.reasons.length > 0 && <ul className="list-disc space-y-1 pl-5 text-sm text-muted">{match.reasons.map((x) => <li key={x}>{x}</li>)}</ul>}
      <Probability value={match.probability} />
      {match.evidence.length > 0 && (
        <div className="space-y-2"><p className="text-sm font-medium">What the résumé says</p>
          {match.evidence.map((e, i) => <EvidenceCard key={`${e.block_id ?? "derived"}-${i}`} evidence={e} />)}</div>
      )}
    </Card>
  );
}

export function AssessmentCard({ assessment: a }: { assessment: Assessment }) {
  return (
    <Card as="article">
      <h3 className="font-serif text-xl">{a.label}</h3>
      <p className="mt-1 text-sm text-muted">{a.summary}</p>
      {a.metrics.length > 0 && (
        <dl className="mt-3 space-y-3">
          {a.metrics.map((m) => (
            <div key={m.name}>
              <dt className="text-sm font-medium">{m.name.replaceAll("_", " ")}: <span className="font-normal">{String(m.value)}{m.unit === "percent" ? "%" : m.unit === "months" ? " months" : ""}</span></dt>
              <dd className="text-sm text-muted">{m.definition}</dd>
            </div>
          ))}
        </dl>
      )}
      {a.limitations.length > 0 && (
        <details className="mt-3 text-sm"><summary className="cursor-pointer text-muted">Where this falls short</summary>
          <ul className="mt-1 list-disc pl-5 text-muted">{a.limitations.map((l) => <li key={l}>{l}</li>)}</ul></details>
      )}
    </Card>
  );
}

export function Warnings({ warnings }: { warnings: Signal[] }) {
  if (warnings.length === 0) return null;
  return (
    <div className="space-y-2">
      {warnings.map((w) => <Notice key={w.code} tone={w.severity === "error" ? "bad" : w.severity === "info" ? "info" : "warn"}>{w.message}</Notice>)}
    </div>
  );
}

export function RecommendationList({ items, editHref }: { items: Recommendation[]; editHref?: string }) {
  if (items.length === 0) return <p className="text-sm text-muted">Nothing to suggest for this analysis.</p>;
  return (
    <ul className="space-y-3">
      {items.map((r, i) => (
        <Card as="li" key={`${r.kind}-${i}`} className="space-y-2">
          <div className="flex flex-wrap items-center gap-2"><Badge tone="plain">{RECOMMENDATION_KIND[r.kind]}</Badge><h3 className="font-medium">{r.title}</h3></div>
          <p className="text-sm">{r.detail}</p>
          {r.excerpt && <blockquote className="rounded-lg bg-raised px-3 py-2 text-sm">{r.excerpt}</blockquote>}
          {r.fill_in && <p className="rounded-lg border border-dashed border-line px-3 py-2 text-sm"><span className="font-medium">A template for you to fill in with true details: </span>{r.fill_in}</p>}
          {editHref && r.block_id && <Link href={`${editHref}#${r.block_id}`} className="text-sm text-accent underline">Edit this line</Link>}
        </Card>
      ))}
    </ul>
  );
}

/** Everything an analysis shows, used for saved analyses and the demo alike. */
export function AnalysisResults(
  { engine, assessments, warnings, matches, limitations, recommendations, recommendationsHref }:
  { engine: EngineInfo | null; assessments: Assessment[] | null; warnings: Signal[]; matches: Match[]; limitations: string[];
    recommendations: Recommendation[]; recommendationsHref?: string },
) {
  const grouped = STATUS_ORDER.map((s) => [s, matches.filter((m) => m.status === s)] as const).filter(([, list]) => list.length > 0);
  return (
    <div className="space-y-8">
      <EnginePanel engine={engine} />
      <Warnings warnings={warnings} />
      {assessments && (
        <section aria-labelledby="readings"><h2 id="readings" className="font-serif text-2xl">Four readings, each explained</h2>
          <p className="mt-1 max-w-prose text-sm text-muted">These describe what was found. None of them is a grade, and they aren't combined into one number.</p>
          <div className="mt-4 grid gap-4 md:grid-cols-2">{assessments.map((a) => <AssessmentCard key={a.id} assessment={a} />)}</div></section>
      )}
      <section aria-labelledby="reqs"><h2 id="reqs" className="font-serif text-2xl">Requirement by requirement</h2>
        {matches.length === 0 && <p className="mt-2 text-muted">No requirements were found in the job description.</p>}
        {grouped.map(([status, list]) => (
          <div key={status} className="mt-5">
            <h3 className="flex items-center gap-2 text-lg font-medium"><StatusBadge status={status} /><span className="text-sm font-normal text-muted">{list.length} · {STATUS[status].hint}</span></h3>
            <ul className="mt-3 space-y-3">{list.map((m) => <RequirementCard key={m.requirement.id} match={m} />)}</ul>
          </div>
        ))}
      </section>
      <section aria-labelledby="recs"><h2 id="recs" className="font-serif text-2xl">Suggestions</h2>
        <p className="mt-1 max-w-prose text-sm text-muted">Each one points at your own words. Nothing here is written for you, and nothing is added to your résumé unless you type it.</p>
        <div className="mt-3"><RecommendationList items={recommendations.slice(0, recommendationsHref ? 3 : undefined)} editHref={recommendationsHref} />
          {recommendationsHref && recommendations.length > 3 && <p className="mt-3"><Link href={recommendationsHref} className="text-accent underline">See all {recommendations.length} suggestions</Link></p>}</div>
      </section>
      {limitations.length > 0 && (
        <section aria-labelledby="limits"><h2 id="limits" className="font-serif text-2xl">Limits to keep in mind</h2>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted">{limitations.map((l) => <li key={l}>{l}</li>)}</ul></section>
      )}
    </div>
  );
}
