"use client";

import Link from "next/link";
import { useId } from "react";
import { friendlyError } from "@/lib/copy";

const cx = (...parts: (string | false | null | undefined)[]) => parts.filter(Boolean).join(" ");

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "quiet" | "danger"; busy?: boolean };

export function Button({ variant = "primary", busy, className, children, disabled, ...rest }: ButtonProps) {
  const styles = {
    primary: "bg-accent text-accent-ink hover:opacity-90",
    secondary: "border border-line bg-surface text-ink hover:bg-raised",
    quiet: "text-accent hover:bg-raised",
    danger: "border border-bad/40 bg-surface text-bad hover:bg-bad/10",
  }[variant];
  return (
    <button
      {...rest}
      disabled={disabled || busy}
      aria-busy={busy || undefined}
      className={cx("inline-flex min-h-[44px] items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-60", styles, className)}
    >
      {busy && <Spinner small />}
      {children}
    </button>
  );
}

export function ButtonLink({ href, children, variant = "primary", className }: { href: string; children: React.ReactNode; variant?: "primary" | "secondary" | "quiet"; className?: string }) {
  const styles = { primary: "bg-accent text-accent-ink hover:opacity-90", secondary: "border border-line bg-surface hover:bg-raised", quiet: "text-accent hover:bg-raised" }[variant];
  return (
    <Link href={href} className={cx("inline-flex min-h-[44px] items-center justify-center rounded-lg px-4 py-2 text-sm font-medium transition", styles, className)}>
      {children}
    </Link>
  );
}

export function Card({ children, className, as: Tag = "section" }: { children: React.ReactNode; className?: string; as?: "section" | "div" | "article" | "li" }) {
  return <Tag className={cx("rounded-xl border border-line bg-surface p-5 shadow-sm", className)}>{children}</Tag>;
}

export function Spinner({ small, label = "Loading" }: { small?: boolean; label?: string }) {
  return (
    <span role="status" className="inline-flex items-center">
      <span aria-hidden className={cx("animate-spin rounded-full border-2 border-current border-t-transparent", small ? "h-4 w-4" : "h-6 w-6")} />
      <span className="sr-only">{label}</span>
    </span>
  );
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return <div className="flex items-center gap-3 py-10 text-muted"><Spinner label={label} /><span aria-hidden>{label}</span></div>;
}

export function EmptyState({ title, children, action }: { title: string; children?: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-line bg-surface px-6 py-12 text-center">
      <h2 className="font-serif text-xl">{title}</h2>
      {children && <p className="mx-auto mt-2 max-w-prose text-muted">{children}</p>}
      {action && <div className="mt-5 flex justify-center">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div role="alert" className="rounded-xl border border-bad/40 bg-bad/5 p-5">
      <h2 className="font-medium text-bad">That didn't work</h2>
      <p className="mt-1 text-sm">{friendlyError(error)}</p>
      {onRetry && <Button variant="secondary" className="mt-3" onClick={onRetry}>Try again</Button>}
    </div>
  );
}

export function Notice({ tone = "info", title, children }: { tone?: "info" | "warn" | "bad" | "good"; title?: string; children: React.ReactNode }) {
  const tones = { info: "border-info/40 bg-info/5", warn: "border-warn/40 bg-warn/5", bad: "border-bad/40 bg-bad/5", good: "border-good/40 bg-good/5" }[tone];
  return (
    <div role={tone === "bad" ? "alert" : "note"} className={cx("rounded-lg border px-4 py-3 text-sm", tones)}>
      {title && <p className="font-medium">{title}</p>}
      <div className={title ? "mt-1" : undefined}>{children}</div>
    </div>
  );
}

export function Badge({ tone = "info", children }: { tone?: "good" | "warn" | "bad" | "info" | "plain"; children: React.ReactNode }) {
  const tones = { good: "bg-good/10 text-good", warn: "bg-warn/10 text-warn", bad: "bg-bad/10 text-bad", info: "bg-info/10 text-info", plain: "bg-raised text-muted" }[tone];
  return <span className={cx("inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium", tones)}>{children}</span>;
}

interface FieldProps { label: string; hint?: string; error?: string | null }

export function TextField({ label, hint, error, ...rest }: FieldProps & React.InputHTMLAttributes<HTMLInputElement>) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium">{label}</label>
      {hint && <p id={`${id}-hint`} className="text-sm text-muted">{hint}</p>}
      <input id={id} {...rest} aria-invalid={!!error || undefined}
        aria-describedby={[hint && `${id}-hint`, error && `${id}-err`].filter(Boolean).join(" ") || undefined}
        className="mt-1 min-h-[44px] w-full rounded-lg border border-line bg-surface px-3 py-2 text-ink placeholder:text-muted" />
      {error && <p id={`${id}-err`} className="mt-1 text-sm text-bad">{error}</p>}
    </div>
  );
}

export function TextArea({ label, hint, error, ...rest }: FieldProps & React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium">{label}</label>
      {hint && <p id={`${id}-hint`} className="text-sm text-muted">{hint}</p>}
      <textarea id={id} {...rest} aria-invalid={!!error || undefined}
        aria-describedby={[hint && `${id}-hint`, error && `${id}-err`].filter(Boolean).join(" ") || undefined}
        className="mt-1 w-full rounded-lg border border-line bg-surface px-3 py-2 text-ink placeholder:text-muted" />
      {error && <p id={`${id}-err`} className="mt-1 text-sm text-bad">{error}</p>}
    </div>
  );
}

export function PageHeader({ title, children, actions }: { title: string; children?: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="font-serif text-3xl leading-tight">{title}</h1>
        {children && <p className="mt-1 max-w-prose text-muted">{children}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </header>
  );
}
