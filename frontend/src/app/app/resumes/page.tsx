"use client";

import Link from "next/link";
import { Icon } from "@/components/icon";
import { useRef, useState } from "react";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Loading,
  Notice,
  PageHeader,
  Pagination,
} from "@/components/ui";
import { api, newIdempotencyKey } from "@/lib/api";
import { failureMessage, formatDate, friendlyError } from "@/lib/copy";
import { useAsync, usePolling } from "@/lib/hooks";

const MAX_BYTES = 5 * 1024 * 1024;

export default function Resumes() {
  const [offset, setOffset] = useState(0);
  const list = useAsync(() => api.resumes(offset), [offset]);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [removing, setRemoving] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const keyRef = useRef<{ file: File; key: string } | null>(null);

  const processing = !!list.data?.items.some((r) => r.latest_version.status === "processing");
  usePolling(processing, list.reload);

  async function onFile(file: File | undefined) {
    if (!file || uploading) return;
    setError(null);
    if (file.size > MAX_BYTES)
      return setError("That file is over 5 MB. Try exporting a smaller PDF.");
    if (!/\.(pdf|docx)$/i.test(file.name))
      return setError(
        "We can read PDF and Word (.docx) files. Could you save yours as one of those?",
      );
    // Re-using the key for the same file makes a retry after a flaky connection safe.
    if (keyRef.current?.file !== file) keyRef.current = { file, key: newIdempotencyKey() };
    setUploading(true);
    try {
      await api.uploadResume(file, keyRef.current.key);
      list.reload();
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setUploading(false);
      if (input.current) input.current.value = "";
    }
  }

  async function remove(id: string, title: string) {
    if (
      !window.confirm(
        `Delete “${title}”, its file and every analysis built on it? This can't be undone.`,
      )
    )
      return;
    setRemoving(id);
    setError(null);
    try {
      await api.deleteResume(id);
      if (offset > 0 && list.data?.items.length === 1) setOffset(Math.max(0, offset - 20));
      else list.reload();
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setRemoving(null);
    }
  }

  return (
    <>
      <PageHeader title="Résumés">
        Upload a PDF or Word file (up to 5 MB). Text-based files work best; scans and photos
        can&apos;t be read.
      </PageHeader>
      <Card className="mb-8 !border-0 !bg-transparent !p-0">
        <div
          className={`upload-zone ${dragging ? "dragging" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            if (!uploading) setDragging(true);
          }}
          onDragLeave={(e) => {
            if (!e.currentTarget.contains(e.relatedTarget as Node)) setDragging(false);
          }}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            if (e.dataTransfer.files.length > 1) {
              setError("Please upload one résumé at a time.");
              return;
            }
            void onFile(e.dataTransfer.files[0]);
          }}
        >
          <Icon name="upload" size={30} />
          <p className="micro-label mb-3">YOUR EXPERIENCE, IN YOUR WORDS</p>
          <label htmlFor="resume-file" className="block font-medium">
            Choose a file
          </label>
          <p className="mb-3 mt-2 text-sm text-muted">
            Drag your résumé here, or browse your files.
          </p>
          <p className="text-sm text-muted">
            Your file is stored privately on this server and only you can open it.
          </p>
          <div className="upload-input-row mt-5 flex flex-wrap items-center gap-3">
            <input
              id="resume-file"
              ref={input}
              type="file"
              accept=".pdf,.docx,application/pdf"
              disabled={uploading}
              onChange={(e) => onFile(e.target.files?.[0])}
              className="max-w-full text-sm file:mr-3 file:min-h-[44px] file:rounded-lg file:border file:border-line file:bg-surface file:px-4"
            />
            {uploading && (
              <span role="status" className="text-sm text-muted">
                Uploading…
              </span>
            )}
          </div>
        </div>
        {error && (
          <div className="mt-3">
            <Notice tone="bad">{error}</Notice>
          </div>
        )}
      </Card>

      {list.loading && <Loading />}
      {!!list.error && <ErrorState error={list.error} onRetry={list.reload} />}
      {list.data && list.data.items.length === 0 && (
        <EmptyState title="No résumés yet">Once you upload one, it shows up here.</EmptyState>
      )}
      {list.data && list.data.items.length > 0 && (
        <ul className="space-y-3" aria-live="polite">
          {list.data.items.map((r) => {
            const v = r.latest_version;
            return (
              <Card
                as="li"
                key={r.id}
                className="flex flex-wrap items-center justify-between gap-3"
              >
                <div>
                  <Link href={`/app/resumes/${r.id}`} className="font-medium text-accent underline">
                    {r.title}
                  </Link>
                  <p className="text-sm text-muted">
                    Uploaded {formatDate(r.created_at)} · version {v.version_no}
                  </p>
                  {v.status === "failed" && (
                    <p className="mt-1 text-sm text-bad">{failureMessage(v.error_code)}</p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {v.status === "processing" && <Badge tone="info">Reading your file…</Badge>}
                  {v.status === "ready" && (
                    <Badge tone={v.parseability?.level === "poor" ? "warn" : "good"}>
                      {v.parseability?.level === "poor" ? "Ready, but hard to read" : "Ready"}
                    </Badge>
                  )}
                  {v.status === "failed" && <Badge tone="bad">Couldn&apos;t read it</Badge>}
                  <Button
                    variant="danger"
                    busy={removing === r.id}
                    onClick={() => remove(r.id, r.title)}
                    aria-label={`Delete ${r.title}`}
                  >
                    Delete
                  </Button>
                </div>
              </Card>
            );
          })}
        </ul>
      )}
      {list.data && <Pagination offset={offset} total={list.data.total} onChange={setOffset} />}
    </>
  );
}
