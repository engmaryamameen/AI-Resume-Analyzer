"use client";
import { useState } from "react";
import { authApi } from "../api";
import { useQuery } from "@/lib/hooks";
import { formatDateTime, friendlyError } from "@/lib/copy";
import { Button, Card, ErrorState, Loading, Notice } from "@/components/ui";

export function SessionList() {
  const sessions = useQuery(["sessions"], (signal) => authApi.sessions(signal));
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState("");
  async function revoke(id: string) {
    if (pending) return;
    setPending(id);
    setError("");
    try {
      await authApi.revokeSession(id);
      sessions.reload();
    } catch (error) {
      setError(friendlyError(error));
    } finally {
      setPending(null);
    }
  }
  return (
    <Card>
      <h2 className="font-sans font-medium text-xl">Active sessions</h2>
      {sessions.loading ? (
        <Loading />
      ) : sessions.error ? (
        <ErrorState error={sessions.error} onRetry={sessions.reload} />
      ) : (
        <ul className="mt-4 space-y-3" aria-busy={sessions.refreshing}>
          {sessions.data?.map((session) => (
            <li key={session.id} className="flex flex-wrap items-center justify-between gap-3">
              <span>
                Signed in {formatDateTime(session.created_at)}
                {session.current ? " · This session" : ""}
              </span>
              {!session.current && (
                <Button
                  variant="quiet"
                  disabled={!!pending}
                  busy={pending === session.id}
                  onClick={() => revoke(session.id)}
                >
                  Sign out session
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      {error && <Notice tone="bad">{error}</Notice>}
    </Card>
  );
}
