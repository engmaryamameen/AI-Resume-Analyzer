"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Badge, Button, ButtonLink, Card, ErrorState, Loading, Notice, PageHeader, TextArea, TextField } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { SECTION_LABEL, failureMessage, formatDate, friendlyError, years } from "@/lib/copy";
import { useAsync, usePolling } from "@/lib/hooks";
import type { ContactField } from "@/lib/types";

function confidenceNote(f: ContactField): string | undefined {
  if (!f.value) return "We couldn't find this. Add it if you'd like it on record.";
  return f.confidence === "high" ? undefined : "Best guess. Please check it.";
}

export default function ResumeReview() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const detail = useAsync(() => api.resume(id), [id]);
  const doc = detail.data?.normalized ?? null;
  const latest = detail.data?.versions.at(-1);

  usePolling(latest?.status === "processing", detail.reload);

  const [contact, setContact] = useState({ name: "", email: "", phone: "" });
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [editing, setEditing] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [message, setMessage] = useState<{ tone: "good" | "bad"; text: string; stale?: boolean } | null>(null);

  useEffect(() => {
    if (!doc) return;
    setContact({ name: doc.contact.name.value ?? "", email: doc.contact.email.value ?? "", phone: doc.contact.phone.value ?? "" });
    setEdits({});
    setEditing(null);
  }, [doc]);

  async function remove() {
    if (!window.confirm("Delete this résumé, its file and every analysis built on it? This can't be undone.")) return;
    setDeleting(true);
    try {
      await api.deleteResume(id);
      router.replace("/app/resumes");
    } catch (e) {
      setMessage({ tone: "bad", text: friendlyError(e) });
      setDeleting(false);
    }
  }

  if (detail.loading) return <Loading />;
  if (detail.error || !detail.data || !latest) return <ErrorState error={detail.error} onRetry={detail.reload} />;
  const r = detail.data;
  const deleteButton = <Button variant="danger" busy={deleting} onClick={remove}>Delete</Button>;

  if (latest.status === "processing") {
    return <><PageHeader title={r.title} actions={deleteButton} /><div aria-live="polite"><Loading label="Reading your file… this usually takes a few seconds." /></div></>;
  }
  if (latest.status !== "ready" || !doc) {
    return (
      <>
        <PageHeader title={r.title} actions={deleteButton} />
        <Notice tone="bad" title="We couldn't read this file">{failureMessage(latest.error_code)}</Notice>
        <p className="mt-4"><Link href="/app/resumes" className="text-accent underline">Back to your résumés</Link></p>
      </>
    );
  }

  const changed = Object.keys(edits).length > 0 || contact.name !== (doc.contact.name.value ?? "") ||
    contact.email !== (doc.contact.email.value ?? "") || contact.phone !== (doc.contact.phone.value ?? "");

  async function save() {
    setSaving(true);
    setMessage(null);
    try {
      const v = await api.correctResume(id, { base_version_no: latest!.version_no, block_edits: edits, contact });
      setMessage({ tone: "good", text: `Saved as version ${v.version_no}. Earlier analyses are kept and marked out of date.` });
      detail.reload();
    } catch (e) {
      setMessage({ tone: "bad", text: friendlyError(e), stale: e instanceof ApiError && e.code === "stale_base_version" });
    } finally {
      setSaving(false);
    }
  }

  const exp = years(doc.total_experience_months);
  return (
    <>
      <PageHeader title={r.title}
        actions={<><ButtonLink href={`/app/analyses/new?resume=${latest.id}`}>Analyse against a job</ButtonLink>{deleteButton}</>}>
        Version {latest.version_no} · uploaded {formatDate(r.created_at)}. Check what was read before you rely on any analysis, and fix anything that's off.
      </PageHeader>

      {latest.parseability && latest.parseability.signals.length > 0 && (
        <div className="mb-6 space-y-2" aria-label="Reading problems">
          {latest.parseability.signals.map((s) => <Notice key={s.code} tone={s.severity === "error" ? "bad" : s.severity === "info" ? "info" : "warn"}>{s.message}</Notice>)}
        </div>
      )}
      {doc.uncertainties.filter((u) => u.severity !== "info").map((u) => <div key={u.code} className="mb-2"><Notice tone="warn">{u.message}</Notice></div>)}
      <div aria-live="polite">
        {message && <div className="mb-4"><Notice tone={message.tone}>{message.text}{message.stale && <> <button className="underline" onClick={detail.reload}>Reload</button></>}</Notice></div>}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-1">
          <Card>
            <h2 className="font-serif text-xl">Contact details</h2>
            <div className="mt-3 space-y-3">
              <TextField label="Name" value={contact.name} hint={confidenceNote(doc.contact.name)} onChange={(e) => setContact({ ...contact, name: e.target.value })} />
              <TextField label="Email" type="email" value={contact.email} hint={confidenceNote(doc.contact.email)} onChange={(e) => setContact({ ...contact, email: e.target.value })} />
              <TextField label="Phone" value={contact.phone} hint={confidenceNote(doc.contact.phone)} onChange={(e) => setContact({ ...contact, phone: e.target.value })} />
            </div>
          </Card>
          <Card>
            <h2 className="font-serif text-xl">At a glance</h2>
            <ul className="mt-2 space-y-1 text-sm">
              <li>Sections found: {doc.sections.filter((s) => s.block_ids.length && s.kind !== "header").length}</li>
              <li>Total experience: {exp ?? "couldn't be worked out from your dates"}</li>
              <li>How readable the file was: <Badge tone={latest.parseability?.level === "good" ? "good" : "warn"}>{latest.parseability?.level ?? "unknown"}</Badge></li>
            </ul>
          </Card>
          <Button onClick={save} busy={saving} disabled={!changed}>Save corrections</Button>
        </div>

        <div className="space-y-6 lg:col-span-2">
          {doc.sections.filter((s) => s.block_ids.length > 0).map((s) => (
            <Card key={s.id}>
              <h2 className="font-serif text-xl">{SECTION_LABEL[s.kind] ?? s.kind}{s.heading && s.heading !== SECTION_LABEL[s.kind] ? <span className="ml-2 text-sm text-muted">(“{s.heading}”)</span> : null}</h2>
              <ul className="mt-3 space-y-2">
                {s.block_ids.map((bid) => {
                  const b = doc.blocks.find((x) => x.id === bid);
                  if (!b) return null;
                  const text = edits[bid] ?? b.text;
                  return (
                    <li key={bid} id={bid} className="rounded-lg bg-raised px-3 py-2">
                      {editing === bid ? (
                        <div className="space-y-2">
                          <TextArea label="Edit this line" rows={3} value={text} onChange={(e) => setEdits({ ...edits, [bid]: e.target.value })} />
                          <Button variant="secondary" onClick={() => setEditing(null)}>Done</Button>
                        </div>
                      ) : (
                        <div className="flex items-start justify-between gap-3">
                          <p className={b.kind === "entry_header" ? "font-medium" : "text-sm"}>{b.kind === "bullet" && "• "}{text}{edits[bid] !== undefined && <> <Badge tone="info">edited</Badge></>}</p>
                          <Button variant="quiet" className="shrink-0" onClick={() => setEditing(bid)} aria-label={`Edit: ${text.slice(0, 40)}`}>Edit</Button>
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            </Card>
          ))}
        </div>
      </div>

      <section className="mt-10" aria-labelledby="versions"><h2 id="versions" className="font-serif text-2xl">Versions</h2>
        <ul className="mt-2 text-sm text-muted">{detail.data.versions.map((v) => <li key={v.id}>Version {v.version_no} · {v.source.replaceAll("_", " ")} · {formatDate(v.created_at)}</li>)}</ul>
      </section>
    </>
  );
}
