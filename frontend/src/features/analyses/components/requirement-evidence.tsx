"use client";
import { Icon } from "@/components/icon";
import { Badge, Card } from "@/components/ui";
import {
  CATEGORY_LABEL,
  EVIDENCE_LABEL,
  PROBABILITY_EXPLANATION,
  ROLE_LABEL,
  SECTION_LABEL,
  STATUS,
  percent,
} from "@/lib/copy";
import type { Evidence, Match, MatchStatus } from "@/lib/types";

export function StatusBadge({ status }: { status: MatchStatus }) {
  const s = STATUS[status];
  return (
    <Badge tone={s.tone}>
      <Icon name={s.icon} size={13} /> {s.label}
    </Badge>
  );
}

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
