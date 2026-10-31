"use client";

import Link from "next/link";
import { Icon } from "./icon";
import { Badge, Card, Notice } from "./ui";
import {
  CATEGORY_LABEL,
  ENGINE_COPY,
  EVIDENCE_LABEL,
  ORIGIN_LABEL,
  PROBABILITY_EXPLANATION,
  RECOMMENDATION_KIND,
  ROLE_LABEL,
  SECTION_LABEL,
  STATUS,
  percent,
} from "@/lib/copy";
import type {
  Assessment,
  EngineInfo,
  Evidence,
  Match,
  MatchStatus,
  Recommendation,
  Signal,
} from "@/lib/types";

export function StatusBadge({ status }: { status: MatchStatus }) {
  const s = STATUS[status];
  return (
    <Badge tone={s.tone}>
      <Icon name={s.icon} size={13} /> {s.label}
    </Badge>
  );
}

/** Shown only when the server sent a calibrated probability. Never used for raw similarity. */
export function Probability({ value }: { value: number | null }) {
  if (value === null || value === undefined) return null;
  return (
    <details className="text-sm">
      <summary className="cursor-pointer text-muted">
        Estimated, calibrated: about {percent(value)} likely to be right{" "}
        <span className="underline">What does this mean?</span>
      </summary>
      <p className="mt-1 max-w-prose text-muted">{PROBABILITY_EXPLANATION}</p>
    </details>
  );
}

export function EnginePanel({
  engine,
  title = "How this was read",
}: {
  engine: EngineInfo | null;
  title?: string;
}) {
  if (!engine) return null;
  const learned = engine.mode !== "rules";
  return (
    <section aria-labelledby="engine-heading" className="surface-card p-6">
      <div className="flex flex-wrap items-center gap-2">
        <h2 id="engine-heading" className="text-xl font-extrabold tracking-tight">
          {title}
        </h2>
        <Badge tone={learned ? "info" : "plain"}>
          {engine.mode === "semantic"
            ? "Local semantic models"
            : learned
              ? "Local models"
              : "Rule-based reading"}
        </Badge>
        {learned && (
          <Badge tone={engine.calibrated ? "good" : "plain"}>
            {engine.calibrated ? "Calibrated estimates" : "No probability estimates"}
          </Badge>
        )}
      </div>
      <p className="mt-2 max-w-prose text-sm text-muted">{ENGINE_COPY[engine.mode]}</p>
      {engine.notes.length > 0 && (
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
          {engine.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      )}
      {learned && engine.models.length > 0 && (
        <table className="mt-3 w-full text-left text-sm">
          <caption className="sr-only">Models used for this analysis</caption>
          <thead>
            <tr className="text-muted">
              <th scope="col" className="pr-3 font-medium">
                Role
              </th>
              <th scope="col" className="pr-3 font-medium">
                Model
              </th>
              <th scope="col" className="pr-3 font-medium">
                Revision
              </th>
              <th scope="col" className="font-medium">
                Licence
              </th>
            </tr>
          </thead>
          <tbody>
            {engine.models.map((m) => (
              <tr key={m.id} className="align-top">
                <th scope="row" className="pr-3 font-medium capitalize">
                  {m.id}
                </th>
                <td className="pr-3">
                  {m.base_model}
                  <br />
                  <span className="text-muted">{ORIGIN_LABEL[m.origin]}</span>
                </td>
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
  const sorted = [...ranges]
    .filter(([a, b]) => a >= 0 && b > a && b <= text.length)
    .sort((x, y) => x[0] - y[0]);
  const parts: React.ReactNode[] = [];
  let at = 0;
  sorted.forEach(([a, b], i) => {
    if (a < at) return;
    if (a > at) parts.push(text.slice(at, a));
    parts.push(
      <mark key={i} className="rounded bg-warn/20 px-0.5 text-ink">
        {text.slice(a, b)}
      </mark>,
    );
    at = b;
  });
  parts.push(text.slice(at));
  return <>{parts}</>;
}

export function EvidenceCard({ evidence: e }: { evidence: Evidence }) {
  return (
    <figure className="rounded-xl border border-accent/10 bg-accent/5 px-4 py-3">
      <blockquote className="text-sm">
        <Highlighted text={e.excerpt} ranges={e.highlights} />
      </blockquote>
      <figcaption className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
        {e.derived ? (
          <span>Worked out from your dates, not quoted</span>
        ) : (
          <>
            {e.section_kind && <span>{SECTION_LABEL[e.section_kind] ?? e.section_kind}</span>}
            {e.label && <span>{EVIDENCE_LABEL[e.label]}</span>}
            {e.roles.length > 0 && (
              <span>{[...new Set(e.roles)].map((r) => ROLE_LABEL[r]).join(", ")}</span>
            )}
          </>
        )}
        {e.page != null && <span>Page {e.page}</span>}
        {e.line != null && <span>Line {e.line}</span>}
        {typeof e.retrieval_score === "number" && (
          <details className="evidence-method">
            <summary>Passage matching details</summary>
            <p>
              match order value {e.retrieval_score.toFixed(2)} · Used to order passages, not a
              probability or a measure of your ability.
            </p>
          </details>
        )}
      </figcaption>
    </figure>
  );
}

export function RequirementCard({
  match,
  expanded = true,
  onToggle,
}: {
  match: Match;
  expanded?: boolean;
  onToggle?: () => void;
}) {
  const r = match.requirement;
  return (
    <Card as="li" className="requirement-card">
      <button
        type="button"
        className="requirement-toggle"
        aria-expanded={expanded}
        onClick={onToggle}
        disabled={!onToggle}
      >
        <span className="requirement-title">
          <h3>{r.text}</h3>
          <span>
            {r.kind === "required" ? "Must-have" : "Nice-to-have"} ·{" "}
            {CATEGORY_LABEL[r.category] ?? r.category}
          </span>
        </span>
        <span className="requirement-toggle-end">
          <StatusBadge status={match.status} />
          {match.conflict && <Badge tone="warn">Conflicting passages</Badge>}
          {onToggle && <Icon name="chevronDown" size={17} />}
        </span>
      </button>
      {expanded && (
        <div className="requirement-detail space-y-3">
          <p className="flex flex-wrap gap-2 text-xs text-muted">
            <span>{r.kind === "required" ? "Must-have" : "Nice-to-have"}</span>
            <span>{CATEGORY_LABEL[r.category] ?? r.category}</span>
            {r.min_years !== null && <span>{r.min_years}+ years</span>}
            {r.origin === "inferred" && <span>inferred from another requirement</span>}
          </p>
          {match.explanation && <p className="text-sm">{match.explanation}</p>}
          {match.reasons.length > 0 && (
            <ul className="list-disc space-y-1 pl-5 text-sm text-muted">
              {match.reasons.map((x) => (
                <li key={x}>{x}</li>
              ))}
            </ul>
          )}
          <Probability value={match.probability} />
          {match.evidence.length > 0 && (
            <div className="space-y-2">
              <p className="text-sm font-medium">What the résumé says</p>
              {match.evidence.map((e, i) => (
                <EvidenceCard key={`${e.block_id ?? "derived"}-${i}`} evidence={e} />
              ))}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

export function AssessmentCard({ assessment: a }: { assessment: Assessment }) {
  return (
    <Card as="article">
      <h3 className="text-xl font-extrabold tracking-tight">
        {a.id === "extraction_reliability" ? "Reading reliability" : a.label}
      </h3>
      <p className="mt-1 text-sm text-muted">{a.summary}</p>
      {a.metrics.length > 0 && (
        <details className="assessment-metrics">
          <summary>
            Explore {a.metrics.length} measurements <Icon name="chevronDown" size={14} />
          </summary>
          <dl className="mt-3 space-y-3">
            {a.metrics.map((m) => (
              <div key={m.name}>
                <dt className="text-sm font-medium">
                  {m.name.replaceAll("_", " ")}:{" "}
                  <span className="font-normal">
                    {String(m.value)}
                    {m.unit === "percent" ? "%" : m.unit === "months" ? " months" : ""}
                  </span>
                </dt>
                <dd className="text-sm text-muted">{m.definition}</dd>
              </div>
            ))}
          </dl>
        </details>
      )}
      {a.limitations.length > 0 && (
        <details className="mt-3 text-sm">
          <summary className="cursor-pointer text-muted">Where this falls short</summary>
          <ul className="mt-1 list-disc pl-5 text-muted">
            {a.limitations.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </details>
      )}
    </Card>
  );
}

export function Warnings({ warnings }: { warnings: Signal[] }) {
  if (warnings.length === 0) return null;
  return (
    <div className="space-y-2">
      {warnings.map((w) => (
        <Notice
          key={w.code}
          tone={w.severity === "error" ? "bad" : w.severity === "info" ? "info" : "warn"}
        >
          {w.message}
        </Notice>
      ))}
    </div>
  );
}

export function RecommendationList({
  items,
  editHref,
  compact = false,
}: {
  items: Recommendation[];
  editHref?: string;
  compact?: boolean;
}) {
  if (items.length === 0)
    return <p className="text-sm text-muted">Nothing to suggest for this analysis.</p>;
  return (
    <ol className="recommendation-list">
      {items.map((r, i) => (
        <Card as="li" key={`${r.kind}-${i}`} className="improvement-card">
          <div className="improvement-heading">
            <span className="improvement-number">{String(i + 1).padStart(2, "0")}</span>
            <div>
              <span className="improvement-kind">{RECOMMENDATION_KIND[r.kind]}</span>
              <h3>{r.title}</h3>
            </div>
          </div>
          <p className="improvement-detail">{r.detail}</p>
          {(r.excerpt || r.fill_in) && (
            <details className="improvement-guide" open={!compact || undefined}>
              <summary>
                See your wording &amp; editing guide <Icon name="chevronDown" size={15} />
              </summary>
              <div>
                {r.excerpt && (
                  <div>
                    <span className="improvement-label">Your current wording</span>
                    <blockquote>{r.excerpt}</blockquote>
                  </div>
                )}
                {r.fill_in && (
                  <div>
                    <span className="improvement-label">Try this structure</span>
                    <p className="improvement-template">{r.fill_in}</p>
                    <p className="improvement-hint">
                      Fill in only what you can support with true details. This is a template, not a
                      suggested claim.
                    </p>
                  </div>
                )}
              </div>
            </details>
          )}
          {editHref && r.block_id && (
            <Link href={`${editHref}#${r.block_id}`} className="improvement-edit">
              Edit this line <Icon name="arrowUpRight" size={14} />
            </Link>
          )}
        </Card>
      ))}
    </ol>
  );
}
