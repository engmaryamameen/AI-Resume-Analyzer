import { SiteFooter, SiteHeader } from "@/components/site-header";
import { ButtonLink } from "@/components/ui";
import { Icon } from "@/components/icon";

export default function NotFound() {
  return (
    <>
      <SiteHeader />
      <main
        id="main"
        className="mx-auto flex min-h-[70vh] max-w-2xl flex-col items-center justify-center px-6 py-20 text-center"
      >
        <span className="micro-label">404 / A MISSING PAGE</span>
        <div className="my-8 text-accent">
          <Icon name="document" size={48} />
        </div>
        <h1 className="font-serif text-4xl tracking-tight">This page has left the paper trail.</h1>
        <p className="mt-5 max-w-md text-sm leading-7 text-muted">
          The address may have changed, or this page is no longer available. Your workspace is a
          good place to pick things up.
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <ButtonLink href="/app">
            Go to your workspace <Icon name="arrow" size={16} />
          </ButtonLink>
          <ButtonLink href="/" variant="secondary">
            Back to overview
          </ButtonLink>
        </div>
      </main>
      <SiteFooter />
    </>
  );
}
