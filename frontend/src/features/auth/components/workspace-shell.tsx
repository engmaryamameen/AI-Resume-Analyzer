"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import { Button, ErrorState, Loading } from "@/components/ui";
import { Icon, type IconName } from "@/components/icon";
import { Brand } from "@/components/site-header";
import { friendlyError } from "@/lib/copy";
import { ApiError } from "@/lib/http/client";
import { authApi } from "@/features/auth/api";
import type { User } from "@/lib/types";
import { UserContext } from "@/lib/user-context";

const NAV: { href: string; label: string; icon: IconName }[] = [
  { href: "/app", label: "Overview", icon: "grid" },
  { href: "/app/resumes", label: "Résumés", icon: "document" },
  { href: "/app/jobs", label: "Target roles", icon: "briefcase" },
  { href: "/app/analyses", label: "Review history", icon: "history" },
  { href: "/app/billing", label: "Review credits", icon: "briefcase" },
  { href: "/app/settings", label: "Settings", icon: "settings" },
];

export function WorkspaceShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const path = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    authApi
      .me(controller.signal)
      .then((user) => {
        if (!controller.signal.aborted) setUser(user);
      })
      .catch((e) => {
        if (controller.signal.aborted) return;
        if (e instanceof ApiError && e.status === 401) router.replace("/login");
        else setError(e);
      });
    return () => controller.abort();
  }, [router, attempt]);

  if (error && !user)
    return (
      <main id="main" className="mx-auto max-w-5xl px-4 py-8">
        <Brand />
        <h1 className="mt-8 mb-5 text-2xl font-medium tracking-tight">
          Unable to open your workspace
        </h1>
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
        <Brand />
        <h1 className="mt-8 mb-5 text-2xl font-medium tracking-tight">Opening your workspace</h1>
        <Loading label="Checking your session…" />
      </main>
    );

  if (user.email_verification_required && !user.email_verified_at)
    return (
      <main id="main" className="mx-auto max-w-md px-4 py-12">
        <h1 className="font-sans font-medium text-3xl">Verify your email</h1>
        <p className="my-5">Open the email link to activate your workspace.</p>
        <Link href="/verify-email" className="text-accent underline">
          Request another verification email
        </Link>
        <SignOutButton />
      </main>
    );

  return (
    <UserContext.Provider value={{ user, setUser }}>
      <div className="workspace-shell product-workspace min-h-screen lg:flex">
        <AppSidebar path={path} user={user} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between border-b border-line bg-surface/70 px-6 py-4 lg:px-10">
            <span className="text-xs font-bold uppercase tracking-[.12em] text-muted">
              Workspace <span className="mx-2 opacity-40">/</span>{" "}
              {path === "/app/analyses/new"
                ? "New analysis"
                : path === "/app/analyses/compare"
                  ? "Compare reviews"
                  : (NAV.find(({ href }) => href !== "/app" && path.startsWith(href))?.label ??
                    "Overview")}
            </span>
            <span className="inline-flex items-center gap-2 text-xs font-semibold text-muted">
              Processed on this server
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

function AppSidebar({ path, user }: { path: string; user: User }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const navigationId = useId();
  const toggle = useRef<HTMLButtonElement>(null);
  return (
    <aside
      className="workspace-sidebar border-b border-line bg-surface lg:sticky lg:top-0 lg:flex lg:h-screen lg:w-[252px] lg:shrink-0 lg:flex-col lg:border-b-0 lg:border-r"
      onKeyDown={(event) => {
        if (event.key === "Escape" && menuOpen) {
          setMenuOpen(false);
          toggle.current?.focus();
        }
      }}
    >
      <div className="workspace-sidebar-heading">
        <Brand />
        <button
          ref={toggle}
          type="button"
          className="workspace-menu-toggle"
          aria-expanded={menuOpen}
          aria-controls={navigationId}
          onClick={() => setMenuOpen(!menuOpen)}
        >
          {menuOpen ? "Close" : "Menu"}
          <Icon name={menuOpen ? "x" : "menu"} size={18} />
        </button>
      </div>
      <div id={navigationId} className="workspace-navigation" data-open={menuOpen}>
        <nav
          aria-label="Workspace"
          className="space-y-1 px-3 pb-4"
          onClick={(event) => {
            if ((event.target as Element).closest("a")) setMenuOpen(false);
          }}
        >
          {NAV.map(({ href, label, icon }) => {
            const active =
              href === "/app"
                ? path === href
                : path.startsWith(href) && path !== "/app/analyses/new";
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className="app-nav-link"
              >
                <span className="workspace-nav-icon">
                  <Icon name={icon} size={19} />
                </span>
                <span>{label}</span>
              </Link>
            );
          })}
        </nav>
        <div className="px-3 pb-5">
          <Link
            href="/app/analyses/new"
            aria-current={path === "/app/analyses/new" ? "page" : undefined}
            onClick={() => setMenuOpen(false)}
            className="flex min-h-[43px] items-center justify-center gap-2 rounded-md bg-[#eeeee9] px-3 py-2 text-sm font-medium text-[#23242b] hover:opacity-90"
          >
            <Icon name="plus" size={17} /> New analysis
          </Link>
        </div>
        <div className="mt-auto border-t border-line px-4 py-5">
          <div className="px-2 py-3">
            <p className="truncate text-xs font-medium">{user.email}</p>
            <p className="mt-1 text-[11px] text-muted">Private workspace</p>
          </div>
          <SignOutButton className="mt-2 w-full" />
        </div>
      </div>
    </aside>
  );
}

function SignOutButton({ className }: { className?: string }) {
  const router = useRouter();
  const [signingOut, setSigningOut] = useState(false);
  const [logoutError, setLogoutError] = useState<string | null>(null);
  async function signOut() {
    if (signingOut) return;
    setSigningOut(true);
    setLogoutError(null);
    try {
      await authApi.logout();
      router.replace("/");
    } catch (e) {
      setLogoutError(friendlyError(e));
    } finally {
      setSigningOut(false);
    }
  }

  return (
    <>
      {" "}
      <Button variant="quiet" className={className} busy={signingOut} onClick={signOut}>
        <Icon name="logout" size={17} />
        Sign out
      </Button>
      {logoutError && (
        <p role="alert" className="workspace-logout-error">
          {logoutError}
        </p>
      )}
    </>
  );
}
