"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button, ErrorState, Loading } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import type { User } from "@/lib/types";
import { UserContext } from "@/lib/user-context";

const NAV = [
  ["/app", "Overview"], ["/app/resumes", "Résumés"], ["/app/jobs", "Jobs"],
  ["/app/analyses", "History"], ["/app/settings", "Settings"],
] as const;

export default function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const path = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    api.me().then(setUser).catch((e) => {
      if (e instanceof ApiError && e.status === 401) router.replace("/login");
      else setError(e);
    });
  }, [router, attempt]);

  if (error && !user) return <main id="main" className="mx-auto max-w-5xl px-4 py-8"><ErrorState error={error} onRetry={() => { setError(null); setAttempt((n) => n + 1); }} /></main>;
  if (!user) return <main id="main" className="mx-auto max-w-5xl px-4"><Loading label="Checking your session…" /></main>;

  return (
    <UserContext.Provider value={{ user, setUser }}>
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <Link href="/app" className="font-serif text-xl">Margin Notes</Link>
          <nav aria-label="Workspace" className="flex flex-wrap gap-1">
            {NAV.map(([href, label]) => {
              const active = href === "/app" ? path === href : path.startsWith(href);
              return (
                <Link key={href} href={href} aria-current={active ? "page" : undefined}
                  className={`rounded-lg px-3 py-2 text-sm ${active ? "bg-raised font-medium" : "hover:bg-raised"}`}>{label}</Link>
              );
            })}
          </nav>
          <Button variant="quiet" onClick={async () => { await api.logout().catch(() => undefined); router.replace("/"); }}>Sign out</Button>
        </div>
      </header>
      <main id="main" className="mx-auto max-w-6xl px-4 py-8">{children}</main>
    </UserContext.Provider>
  );
}
