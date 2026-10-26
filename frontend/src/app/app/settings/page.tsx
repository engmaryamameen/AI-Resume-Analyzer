"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ModelStatusPanel } from "@/components/model-status";
import { Button, Card, Notice, PageHeader, TextField } from "@/components/ui";
import { api } from "@/lib/api";
import { friendlyError } from "@/lib/copy";
import { useUser } from "@/lib/user-context";

export default function Settings() {
  const { user } = useUser();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function deleteAccount(e: React.FormEvent) {
    e.preventDefault();
    if (!window.confirm("Delete your account and everything in it? This can't be undone.")) return;
    setBusy(true);
    setError(null);
    try {
      await api.deleteAccount(password);
      router.replace("/");
    } catch (err) {
      // A wrong password is a 403: the session is still good, so stay here and say so.
      setError(friendlyError(err));
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title="Account and privacy">You're signed in as {user.email}.</PageHeader>
      <div className="space-y-6">
        <Card>
          <h2 className="font-serif text-xl">Where your data goes</h2>
          <p className="mt-1 max-w-prose text-muted">
            Your documents are analysed on this server by models stored on it. Nothing is sent to an outside AI service.{" "}
            <Link href="/privacy" className="text-accent underline">Read the full privacy notes</Link>.
          </p>
        </Card>
        <ModelStatusPanel />
        <Card>
          <h2 className="font-serif text-xl">Delete everything</h2>
          <p className="mt-1 max-w-prose text-muted">
            This permanently removes your account, uploaded files, extracted text, job descriptions and all analyses. It can't be undone, and reports you downloaded stay with you.
          </p>
          <form onSubmit={deleteAccount} className="mt-4 max-w-sm space-y-3">
            <TextField label="Your password" type="password" autoComplete="current-password" required value={password}
              hint="We ask for it again before deleting anything." onChange={(e) => setPassword(e.target.value)} />
            <div aria-live="polite">{error && <Notice tone="bad">{error}</Notice>}</div>
            <Button type="submit" variant="danger" disabled={password === ""} busy={busy}>Delete my account and data</Button>
          </form>
        </Card>
      </div>
    </>
  );
}
