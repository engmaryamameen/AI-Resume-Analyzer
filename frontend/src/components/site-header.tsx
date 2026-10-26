import Link from "next/link";
import { ButtonLink } from "./ui";

export function SiteHeader() {
  return (
    <header className="border-b border-line bg-surface">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
        <Link href="/" className="font-serif text-xl">Margin Notes</Link>
        <nav aria-label="Main" className="flex items-center gap-2">
          <Link href="/demo" className="rounded-lg px-3 py-2 text-sm hover:bg-raised">Try the demo</Link>
          <Link href="/privacy" className="hidden rounded-lg px-3 py-2 text-sm hover:bg-raised sm:inline-block">Privacy</Link>
          <ButtonLink href="/login" variant="secondary">Sign in</ButtonLink>
        </nav>
      </div>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="border-t border-line">
      <div className="mx-auto max-w-6xl px-4 py-8 text-sm text-muted">
        <p>Margin Notes compares the wording of a résumé with the wording of a job description. It can't tell you whether you'll be hired, and it doesn't claim to.</p>
      </div>
    </footer>
  );
}
