"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button, ErrorState, Loading } from "@/components/ui";
import { Icon, type IconName } from "@/components/icon";
import { Brand } from "@/components/site-header";
import { friendlyError } from "@/lib/copy";
import { api, ApiError } from "@/lib/api";
import type { User } from "@/lib/types";
import { UserContext } from "@/lib/user-context";

const NAV = [
  ["/app", "Overview"],
  ["/app/resumes", "Résumés"],
  ["/app/jobs", "Target roles"],
  ["/app/analyses", "Review history"],
  ["/app/settings", "Settings"],
] as const;

export default function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const path = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [attempt, setAttempt] = useState(0);
  const [signingOut, setSigningOut] = useState(false);
  const [logoutError, setLogoutError] = useState<string | null>(null);
  async function signOut() {
    if (signingOut) return;
    setSigningOut(true);
    setLogoutError(null);
    try {
      await api.logout();
      router.replace("/");
    } catch (e) {
      setLogoutError(friendlyError(e));
    } finally {
      setSigningOut(false);
    }
  }

  useEffect(() => {
    api
      .me()
      .then(setUser)
      .catch((e) => {
        if (e instanceof ApiError && e.status === 401) router.replace("/login");
        else setError(e);
      });
  }, [router, attempt]);

  if (error && !user)
    return (
      <main id="main" className="mx-auto max-w-5xl px-4 py-8">
        <ErrorState
          error={error}
          onRetry={() => {
            setError(null);
            setAttempt((n) => n + 1);
          }}
        />
      </main>
    );
  if (!user)
    return (
      <main id="main" className="mx-auto max-w-5xl px-4">
        <Loading label="Checking your session…" />
      </main>
    );

  return (
    <UserContext.Provider value={{ user, setUser }}>
      <div className="workspace-shell rolemark-workspace min-h-screen lg:flex">
        <aside className="border-b border-line bg-surface lg:sticky lg:top-0 lg:flex lg:h-screen lg:w-[252px] lg:shrink-0 lg:flex-col lg:border-b-0 lg:border-r">
          <div className="px-6 py-6">
            <Brand />
          </div>
          <div className="px-4 pb-2 pt-2 text-[10px] font-extrabold uppercase tracking-[.18em] text-muted">
            Workspace
          </div>
          <nav
            aria-label="Workspace"
            className="flex flex-wrap gap-1 px-3 pb-4 lg:block lg:space-y-1"
          >
            {NAV.map(([href, label], i) => {
              const active = href === "/app" ? path === href : path.startsWith(href);
              const symbol: IconName =
                (["grid", "document", "briefcase", "history", "settings"] as const)[i] ??
                "document";
              return (
                <Link
                  key={href}
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className="app-nav-link"
                >
                  <span className="workspace-nav-icon">
                    <Icon name={symbol} size={20} />
                  </span>
                  <span>{label}</span>
                </Link>
              );
            })}
          </nav>
          <div className="hidden px-3 lg:block">
            <Link
              href="/app/analyses/new"
              className="flex min-h-[43px] items-center justify-center gap-2 rounded-xl bg-accent px-3 py-2 text-sm font-semibold text-white hover:opacity-90"
            >
              <span className="workspace-create-icon">
                <Icon name="plus" size={17} />
              </span>{" "}
              New analysis
            </Link>
          </div>
          <div className="mt-auto hidden border-t border-line px-4 py-5 lg:block">
            <div className="rounded-md border border-line bg-raised p-3">
              <p className="truncate text-xs font-bold">{user.email}</p>
              <p className="mt-1 text-[11px] text-muted">Private workspace</p>
            </div>
            <Button variant="quiet" className="mt-2 w-full" busy={signingOut} onClick={signOut}>
              <Icon name="logout" size={17} />
              Sign out
            </Button>
            {logoutError && (
              <p role="alert" className="workspace-logout-error">
                {logoutError}
              </p>
            )}
          </div>
          <div className="px-4 pb-3 lg:hidden">
            <Button variant="quiet" busy={signingOut} onClick={signOut}>
              <Icon name="logout" size={17} />
              Sign out
            </Button>
            {logoutError && (
              <p role="alert" className="workspace-logout-error">
                {logoutError}
              </p>
            )}
          </div>
        </aside>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between border-b border-line bg-surface/70 px-6 py-4 lg:px-10">
            <span className="text-xs font-bold uppercase tracking-[.12em] text-muted">
              Workspace <span className="mx-2 opacity-40">/</span>{" "}
              {NAV.find(([href]) => href !== "/app" && path.startsWith(href))?.[1] ?? "Overview"}
            </span>
            <span className="inline-flex items-center gap-2 text-xs font-semibold text-muted">
              <span className="h-2 w-2 rounded-full bg-accent" /> Local processing
            </span>
          </div>
          <main id="main" className="mx-auto w-full max-w-7xl px-5 py-9 lg:px-10 lg:py-11">
            {children}
          </main>
        </div>
      </div>
    </UserContext.Provider>
  );
}
