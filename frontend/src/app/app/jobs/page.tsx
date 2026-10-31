"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  Loading,
  Notice,
  PageHeader,
  Pagination,
  TextArea,
  TextField,
} from "@/components/ui";
import { api } from "@/lib/api";
import { formatDate, friendlyError } from "@/lib/copy";
import { useAsync } from "@/lib/hooks";

export default function Jobs() {
  const router = useRouter();
  const [offset, setOffset] = useState(0);
  const list = useAsync(() => api.jobs(offset), [offset]);
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const job = await api.createJob(title || "Untitled role", text);
      router.push(`/app/jobs/${job.id}`);
    } catch (err) {
      setError(friendlyError(err));
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title="Target roles">
        Paste a posting. The requirements are picked out of it, and you get to correct anything
        that&apos;s wrong.
      </PageHeader>
      <Card className="mb-8">
        <form onSubmit={create} className="space-y-4">
          <TextField
            label="Role name"
            placeholder="e.g. Backend engineer at Acme"
            value={title}
            maxLength={200}
            onChange={(e) => setTitle(e.target.value)}
          />
          <TextArea
            label="Job description"
            rows={9}
            required
            value={text}
            maxLength={20000}
            hint="Paste the whole posting, including the nice-to-haves."
            onChange={(e) => setText(e.target.value)}
          />
          {error && <Notice tone="bad">{error}</Notice>}
          <Button type="submit" busy={busy} disabled={text.trim().length < 40}>
            Find the requirements
          </Button>
        </form>
      </Card>
      {list.loading && <Loading />}
      {!!list.error && <ErrorState error={list.error} onRetry={list.reload} />}
      {list.data && list.data.items.length === 0 && (
        <EmptyState title="No job descriptions yet">Paste one above to get started.</EmptyState>
      )}
      <ul className="space-y-3">
        {list.data?.items.map((j) => (
          <Card as="li" key={j.id}>
            <Link href={`/app/jobs/${j.id}`} className="font-medium text-accent underline">
              {j.title}
            </Link>
            <p className="text-sm text-muted">
              Added {formatDate(j.created_at)} · version {j.latest_version.version_no}
            </p>
          </Card>
        ))}
      </ul>
      {list.data && <Pagination offset={offset} total={list.data.total} onChange={setOffset} />}
    </>
  );
}
