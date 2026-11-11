"use client";
import { Icon } from "@/components/icon";
import { Badge, Card, Notice } from "@/components/ui";
import { ENGINE_COPY, ORIGIN_LABEL } from "@/lib/copy";
import type { Assessment, EngineInfo, Signal } from "@/lib/types";

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
