"use client";

import { useId, useState } from "react";
import Link from "next/link";
import { Select } from "./select";
import { Icon } from "./icon";
import { Pagination } from "./ui";
import {
  AssessmentCard,
  EnginePanel,
  RecommendationList,
  RequirementCard,
  StatusBadge,
  Warnings,
} from "./analysis-widgets";
import { STATUS, STATUS_ORDER } from "@/lib/copy";
import type {
  Assessment,
  EngineInfo,
  Match,
  MatchStatus,
  Recommendation,
  Signal,
} from "@/lib/types";

/** Everything an analysis shows, used for saved analyses and the demo alike. */
export function AnalysisResults({
  engine,
  assessments,
  warnings,
  matches,
  limitations,
  recommendations,
  recommendationsHref,
}: {
  engine: EngineInfo | null;
  assessments: Assessment[] | null;
  warnings: Signal[];
  matches: Match[];
  limitations: string[];
  recommendations: Recommendation[];
  recommendationsHref?: string;
}) {
  const [tab, setTab] = useState<"overview" | "evidence" | "suggestions" | "insights">("overview");
  const tabsId = useId();
  const tabs = [
    { id: "overview" as const, label: "Next steps", icon: "check" as const },
    { id: "evidence" as const, label: "Evidence", icon: "search" as const },
    { id: "suggestions" as const, label: "Suggestions", icon: "document" as const },
    { id: "insights" as const, label: "Document insights", icon: "grid" as const },
  ];
  const gapCount = matches.filter(
    (m) => m.status === "no_evidence" || m.status === "contradicted",
  ).length;
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<MatchStatus | "all">("all");
  const [kind, setKind] = useState("all");
  const [page, setPage] = useState(0);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [allSuggestions, setAllSuggestions] = useState(false);
  const searchId = useId();
  const kindId = useId();
  const visible = matches.filter(
    (m) =>
      (filter === "all" || m.status === filter) &&
      (kind === "all" || m.requirement.kind === kind) &&
      [m.requirement.text, ...m.requirement.terms, ...m.evidence.map((e) => e.excerpt)]
        .join(" ")
        .toLowerCase()
        .includes(query.toLowerCase().trim()),
  );
  const ordered = STATUS_ORDER.flatMap((s) => visible.filter((m) => m.status === s));
  const pageOffset = Math.min(page, Math.max(0, Math.ceil(ordered.length / 6) - 1) * 6);
  const pageMatches = ordered.slice(pageOffset, pageOffset + 6);
  const grouped = STATUS_ORDER.map(
    (s) => [s, pageMatches.filter((m) => m.status === s)] as const,
  ).filter(([, list]) => list.length > 0);
  return (
    <div className="analysis-report space-y-7">
      <section className="report-at-glance" aria-label="Analysis at a glance">
        <div>
          <Icon name="check" size={18} />
          <strong>{matches.filter((m) => m.status === "supported").length}</strong>
          <span>Backed by evidence</span>
        </div>
        <div>
          <Icon name="search" size={18} />
          <strong>
            {
              matches.filter((m) => m.status === "mentioned_only" || m.status === "insufficient")
                .length
            }
          </strong>
          <span>Need a closer look</span>
        </div>
        <div>
          <Icon name="document" size={18} />
          <strong>
            {
              matches.filter((m) => m.status === "no_evidence" || m.status === "contradicted")
                .length
            }
          </strong>
          <span>Missing or conflicting</span>
        </div>
      </section>
      <Warnings warnings={warnings.filter((w) => w.severity !== "info")} />
      <div className="report-tabs" role="tablist" aria-label="Review sections">
        {tabs.map((item, index) => (
          <button
            type="button"
            key={item.id}
            id={`${tabsId}-${item.id}`}
            role="tab"
            aria-selected={tab === item.id}
            aria-controls={`${tabsId}-${item.id}-panel`}
            tabIndex={tab === item.id ? 0 : -1}
            onClick={() => setTab(item.id)}
            onKeyDown={(event) => {
              const next =
                event.key === "ArrowRight"
                  ? (index + 1) % tabs.length
                  : event.key === "ArrowLeft"
                    ? (index + tabs.length - 1) % tabs.length
                    : event.key === "Home"
                      ? 0
                      : event.key === "End"
                        ? tabs.length - 1
                        : null;
              if (next !== null) {
                event.preventDefault();
                const target = tabs[next]!;
                setTab(target.id);
                document.getElementById(`${tabsId}-${target.id}`)?.focus();
              }
            }}
          >
            <Icon name={item.icon} size={15} />
            {item.label}
            {item.id === "suggestions" && recommendations.length > 0 && (
              <span>{recommendations.length}</span>
            )}
          </button>
        ))}
      </div>
      <div
        hidden={tab !== "overview"}
        role="tabpanel"
        id={`${tabsId}-overview-panel`}
        aria-labelledby={`${tabsId}-overview`}
        tabIndex={0}
      >
        <section className="next-steps" aria-labelledby={`${tabsId}-next-heading`}>
          <div className="next-steps-heading">
            <span className="improvement-label">YOUR EDITING PLAN</span>
            <h2 id={`${tabsId}-next-heading`}>
              {recommendations.length
                ? "Start with these improvements"
                : "Your review, in perspective"}
            </h2>
            <p>
              {recommendations.length
                ? "Make one useful edit at a time. These suggestions come from the wording in your résumé."
                : "No specific edits were identified by this reader. Check the evidence and any gaps before deciding what to change."}
            </p>
          </div>
          <RecommendationList
            items={recommendations.slice(0, 3)}
            editHref={recommendationsHref}
            compact
          />
          {recommendations.length > 3 && (
            <button
              type="button"
              className="report-next-link"
              onClick={() => setTab("suggestions")}
            >
              View all {recommendations.length} suggestions <Icon name="arrow" size={15} />
            </button>
          )}
          {matches.some((m) => m.status === "no_evidence" || m.status === "contradicted") && (
            <div className="review-gap-note">
              <Icon name="search" size={20} />
              <div>
                <h3>Check what the reader couldn’t find</h3>
                <p>
                  {gapCount} {gapCount === 1 ? "requirement has" : "requirements have"} missing or
                  conflicting evidence. A gap in the text does not mean you lack the experience. Add
                  relevant examples only if they are accurate.
                </p>
                <button
                  type="button"
                  className="report-next-link"
                  onClick={() => {
                    setFilter("all");
                    setKind("all");
                    setQuery("");
                    setPage(0);
                    setTab("evidence");
                  }}
                >
                  Review the requirements <Icon name="arrow" size={14} />
                </button>
              </div>
            </div>
          )}
        </section>
      </div>
      <div
        hidden={tab !== "insights"}
        role="tabpanel"
        id={`${tabsId}-insights-panel`}
        aria-labelledby={`${tabsId}-insights`}
        tabIndex={0}
      >
        {assessments && (
          <section aria-labelledby="readings">
            <h2 id="readings" className="font-serif text-2xl">
              Four readings, at a glance
            </h2>
            <p className="mt-1 max-w-prose text-sm text-muted">
              These describe what was found. None of them is a grade, and they aren&apos;t combined
              into one number.
            </p>
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              {assessments.map((a) => (
                <AssessmentCard key={a.id} assessment={a} />
              ))}
            </div>
          </section>
        )}
      </div>
      <div
        hidden={tab !== "evidence"}
        role="tabpanel"
        id={`${tabsId}-evidence-panel`}
        aria-labelledby={`${tabsId}-evidence`}
        tabIndex={0}
      >
        <section aria-labelledby="reqs">
          <h2 id="reqs" className="font-serif text-2xl">
            Requirement by requirement
          </h2>
          {matches.length > 0 && (
            <>
              <div className="evidence-summary" aria-label="Filter by finding status">
                <button
                  type="button"
                  aria-pressed={filter === "all"}
                  onClick={() => {
                    setFilter("all");
                    setPage(0);
                  }}
                >
                  All findings<strong>{matches.length}</strong>
                </button>
                {STATUS_ORDER.filter((s) => matches.some((m) => m.status === s)).map((s) => (
                  <button
                    key={s}
                    type="button"
                    aria-pressed={filter === s}
                    onClick={() => {
                      setFilter(s);
                      setPage(0);
                    }}
                  >
                    {STATUS[s].label}
                    <strong>{matches.filter((m) => m.status === s).length}</strong>
                  </button>
                ))}
              </div>
              <div className="evidence-toolbar">
                <label htmlFor={searchId} className="evidence-search">
                  <Icon name="search" size={16} />
                  <span className="sr-only">Search requirements and evidence</span>
                  <input
                    id={searchId}
                    type="search"
                    placeholder="Search requirements or source text…"
                    value={query}
                    onChange={(e) => {
                      setQuery(e.target.value);
                      setPage(0);
                    }}
                  />
                </label>
                <label className="sr-only" htmlFor={kindId}>
                  Requirement priority
                </label>
                <Select
                  id={kindId}
                  value={kind}
                  onChange={(value) => {
                    setKind(value);
                    setPage(0);
                  }}
                >
                  <option value="all">All priorities</option>
                  <option value="required">Must-have</option>
                  <option value="preferred">Nice-to-have</option>
                </Select>
              </div>
              <p role="status" className="text-xs text-muted">
                Showing {visible.length} of {matches.length} requirements
              </p>
              {visible.length === 0 && (
                <div className="mt-4 rounded-lg border border-dashed border-line p-6 text-sm text-muted">
                  No requirements match these filters.{" "}
                  <button
                    type="button"
                    className="text-accent underline"
                    onClick={() => {
                      setQuery("");
                      setFilter("all");
                      setKind("all");
                    }}
                  >
                    Clear filters
                  </button>
                </div>
              )}
            </>
          )}
          {matches.length === 0 && (
            <p className="mt-2 text-muted">No requirements were found in the job description.</p>
          )}
          <p className="mt-3 text-xs text-muted">
            Select a requirement to read the source evidence and explanation.
          </p>
          {grouped.map(([status, list]) => (
            <div key={status} className="mt-5">
              <h3 className="flex items-center gap-2 text-lg font-medium">
                <StatusBadge status={status} />
                <span className="text-sm font-normal text-muted">
                  {list.length} · {STATUS[status].hint}
                </span>
              </h3>
              <ul className="mt-3 space-y-3">
                {list.map((m) => (
                  <RequirementCard
                    key={m.requirement.id}
                    match={m}
                    expanded={expanded === m.requirement.id}
                    onToggle={() =>
                      setExpanded(expanded === m.requirement.id ? null : m.requirement.id)
                    }
                  />
                ))}
              </ul>
            </div>
          ))}
          <Pagination offset={pageOffset} total={visible.length} limit={6} onChange={setPage} />
        </section>
      </div>
      <div
        hidden={tab !== "suggestions"}
        role="tabpanel"
        id={`${tabsId}-suggestions-panel`}
        aria-labelledby={`${tabsId}-suggestions`}
        tabIndex={0}
      >
        <section aria-labelledby="recs">
          <h2 id="recs" className="font-serif text-2xl">
            Suggestions
          </h2>
          <p className="mt-1 max-w-prose text-sm text-muted">
            Use these as an editing checklist. Open a guide to see your original wording and a
            structure you can fill in with true details.
          </p>
          <div className="mt-3">
            <RecommendationList
              items={recommendations.slice(0, allSuggestions ? undefined : 3)}
              editHref={recommendationsHref}
              compact
            />
            {recommendations.length > 3 && (
              <p className="mt-3">
                {recommendationsHref ? (
                  <Link href={recommendationsHref} className="text-accent underline">
                    See all {recommendations.length} suggestions
                  </Link>
                ) : (
                  <button
                    type="button"
                    className="report-text-button"
                    onClick={() => setAllSuggestions(!allSuggestions)}
                  >
                    {allSuggestions
                      ? "Show fewer suggestions"
                      : `See all ${recommendations.length} suggestions`}
                    <Icon name="chevronDown" size={14} />
                  </button>
                )}
              </p>
            )}
          </div>
        </section>
      </div>
      <details className="report-disclosure">
        <summary>
          <span>
            <Icon name="shield" size={18} />
            <h2>How this was read</h2>
          </span>
          <span>
            {engine && engine.mode !== "rules" ? "Local models" : "Rule-based reading"}
            <Icon name="chevronDown" size={16} />
          </span>
        </summary>
        <div>
          <EnginePanel engine={engine} title="Processing details" />
          <Warnings warnings={warnings.filter((w) => w.severity === "info")} />
        </div>
      </details>
      {limitations.length > 0 && (
        <details className="report-disclosure">
          <summary>
            <h2 id="limits">Limits to keep in mind</h2>
            <Icon name="chevronDown" size={16} />
          </summary>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted">
            {limitations.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
