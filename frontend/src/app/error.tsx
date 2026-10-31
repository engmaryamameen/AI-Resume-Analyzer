"use client";

import { Button, ButtonLink } from "@/components/ui";
import { Icon } from "@/components/icon";

export default function ErrorPage({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main
      id="main"
      className="mx-auto flex min-h-[80vh] max-w-xl flex-col items-center justify-center px-6 py-16 text-center"
    >
      <Icon name="document" size={42} />
      <span className="micro-label mt-7">AN UNEXPECTED INTERRUPTION</span>
      <h1 className="mt-5 font-serif text-4xl tracking-tight">Let’s pick up that thread.</h1>
      <p className="mt-5 text-sm leading-7 text-muted">
        This page couldn’t finish loading. Try it again, or return to your workspace to continue.
      </p>
      <div className="mt-8 flex gap-3">
        <Button onClick={reset}>Try again</Button>
        <ButtonLink href="/app" variant="secondary">
          Your workspace
        </ButtonLink>
      </div>
    </main>
  );
}
