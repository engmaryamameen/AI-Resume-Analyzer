"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Badge, Button, ButtonLink, Card, ErrorState, Loading, Notice, PageHeader, TextField } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { CATEGORY_LABEL, formatDate, friendlyError } from "@/lib/copy";
import { useAsync } from "@/lib/hooks";
import type { RequirementCategory, RequirementKind, RequirementOrigin } from "@/lib/types";

interface Row {
  id?: string; text: string; kind: RequirementKind; category: RequirementCategory; origin: RequirementOrigin;
  minYears: string; span?: { start?: number; end?: number }; reason?: string;
}

export default function JobDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [version, setVersion] = useState<number | undefined>(undefined);
  const job = useAsync(() => api.job(id, version), [id, version]);
  const [rows, setRows] = useState<Row[]>([]);
  const [focus, setFocus] = useState<{ start: number; end: number } | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [msg, setMsg] = useState<{ tone: "good" | "bad"; text: string } | null>(null);

  useEffect(() => {
    if (!job.data) return;
    setRows(job.data.requirements.map((r) => ({
      id: r.id, text: r.text, kind: r.kind, category: r.category, origin: r.origin,
      minYears: r.min_years === null ? "" : String(r.min_years), span: r.source_span ?? undefined, reason: r.source_span?.reason,
    })));
    setFocus(null);
  }, [job.data]);

  if (job.loading) return <Loading />;
  if (job.error || !job.data) return <ErrorState error={job.error} onRetry={job.reload} />;
  const j = job.data;
  const latestNo = j.versions.at(-1)!.version_no;
  const viewing = version !== undefined && version !== latestNo;
  const shownNo = version ?? latestNo;

  const update = (i: number, patch: Partial<Row>) => setRows((rs) => rs.map((r, n) => (n === i ? { ...r, ...patch } : r)));

  async function save() {
    setSaving(true);
    setMsg(null);
    try {
      const keep = rows.filter((r) => r.origin !== "inferred" && r.text.trim().length >= 2).map((r) => ({
        id: r.id, text: r.text.trim(), kind: r.kind, category: r.category,
        min_years: r.minYears.trim() === "" ? null : Number(r.minYears),
      }));
      await api.saveRequirements(id, latestNo, keep);
      setMsg({ tone: "good", text: "Saved as a new version. Earlier analyses keep the version they used." });
      job.reload();
    } catch (e) {
      setMsg({ tone: "bad", text: friendlyError(e) + (e instanceof ApiError && e.code === "stale_base_version" ? " Reload to continue." : "") });
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    if (!window.confirm("Delete this job description and every analysis that used it?")) return;
    setDeleting(true);
    try {
      await api.deleteJob(id);
      router.replace("/app/jobs");
    } catch (e) {
      setMsg({ tone: "bad", text: friendlyError(e) });
      setDeleting(false);
    }
  }

  const raw = j.raw_text;
  return (
    <>
      <PageHeader title={j.title} actions={<><ButtonLink href={`/app/analyses/new?job=${j.versions.at(-1)!.id}`}>Analyse a résumé</ButtonLink><Button variant="danger" busy={deleting} onClick={remove}>Delete</Button></>}>
        Here's what was picked out of the posting. Remove anything that isn't really a requirement, fix the wording, or add something that was missed.
      </PageHeader>
      {j.warnings.map((w) => <div key={w.code} className="mb-3"><Notice tone="warn">{w.message}</Notice></div>)}
      <div aria-live="polite">{msg && <div className="mb-4"><Notice tone={msg.tone}>{msg.text}</Notice></div>}</div>
      {viewing && <div className="mb-4"><Notice tone="info">You are looking at version {shownNo}, which is read-only. <button className="underline" onClick={() => setVersion(undefined)}>Back to the latest</button></Notice></div>}

      <ul className="space-y-3">
        {rows.map((r, i) => (
          <Card as="li" key={r.id ?? `new-${i}`} className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="plain">{CATEGORY_LABEL[r.category] ?? r.category}</Badge>
              {r.origin === "extracted" && <Badge tone="plain">Found in the posting</Badge>}
              {r.origin === "inferred" && <Badge tone="plain">Inferred: {r.reason ?? "implied by another requirement"}</Badge>}
              {r.origin === "user" && <Badge tone="info">Added by you</Badge>}
              {r.span?.start !== undefined && r.span.end !== undefined && (
                <Button variant="quiet" className="!min-h-0 !py-1" onClick={() => setFocus({ start: r.span!.start!, end: r.span!.end! })}>Show where in the posting</Button>
              )}
            </div>
            <TextField label="Requirement" value={r.text} disabled={r.origin === "inferred" || viewing} onChange={(e) => update(i, { text: e.target.value })} />
            <div className="flex flex-wrap items-end gap-4">
              <div>
                <label htmlFor={`kind-${i}`} className="block text-sm font-medium">How important</label>
                <select id={`kind-${i}`} value={r.kind} disabled={r.origin === "inferred" || viewing} onChange={(e) => update(i, { kind: e.target.value as RequirementKind })}
                  className="mt-1 min-h-[44px] rounded-lg border border-line bg-surface px-3">
                  <option value="required">Must-have</option><option value="preferred">Nice-to-have</option>
                </select>
              </div>
              <div>
                <label htmlFor={`cat-${i}`} className="block text-sm font-medium">Kind of requirement</label>
                <select id={`cat-${i}`} value={r.category} disabled={r.origin === "inferred" || viewing} onChange={(e) => update(i, { category: e.target.value as RequirementCategory })}
                  className="mt-1 min-h-[44px] rounded-lg border border-line bg-surface px-3">
                  {Object.entries(CATEGORY_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </div>
              {r.category === "experience_years" && (
                <div className="w-32"><TextField label="Minimum years" inputMode="decimal" value={r.minYears} disabled={viewing} onChange={(e) => update(i, { minYears: e.target.value })} /></div>
              )}
              {r.origin !== "inferred" && !viewing && <Button variant="quiet" onClick={() => setRows(rows.filter((_, n) => n !== i))}>Remove</Button>}
            </div>
          </Card>
        ))}
      </ul>
      {!viewing && (
        <div className="mt-4 flex flex-wrap gap-3">
          <Button variant="secondary" onClick={() => setRows([...rows, { text: "", kind: "required", category: "skill", origin: "user", minYears: "" }])}>Add a requirement</Button>
          <Button onClick={save} busy={saving}>Save changes</Button>
        </div>
      )}

      <section className="mt-10" aria-labelledby="posting"><h2 id="posting" className="font-serif text-2xl">The original posting</h2>
        <pre className="mt-3 whitespace-pre-wrap rounded-xl border border-line bg-surface p-4 text-sm">
          {focus && focus.end <= raw.length ? <>{raw.slice(0, focus.start)}<mark className="rounded bg-warn/20 px-0.5 text-ink">{raw.slice(focus.start, focus.end)}</mark>{raw.slice(focus.end)}</> : raw}
        </pre>
      </section>

      <section className="mt-10" aria-labelledby="jv"><h2 id="jv" className="font-serif text-2xl">Versions</h2>
        <ul className="mt-2 space-y-1 text-sm">
          {j.versions.map((v) => (
            <li key={v.id}>Version {v.version_no} · {v.source.replaceAll("_", " ")} · {formatDate(v.created_at)}{" "}
              {v.version_no !== shownNo && <button className="text-accent underline" onClick={() => setVersion(v.version_no === latestNo ? undefined : v.version_no)}>View</button>}
              {v.version_no === shownNo && <Badge tone="plain">viewing</Badge>}</li>
          ))}
        </ul>
      </section>
    </>
  );
}
