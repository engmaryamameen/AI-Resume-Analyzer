"use client";

import { useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { billingApi } from "@/features/billing/api";
import { Button, Card, ErrorState, Loading, Notice, PageHeader } from "@/components/ui";
import { usePolling, useQuery } from "@/lib/hooks";
import { newIdempotencyKey } from "@/lib/http/client";
import { friendlyError } from "@/lib/copy";

export default function Billing() {
  const query = useQuery(["billing"], billingApi.status);
  const returned = useSearchParams().get("checkout");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const key = useRef<string | null>(null);
  usePolling(returned === "returned" && query.data?.enabled === true, query.reload, 5000);
  async function checkout() {
    setBusy(true);
    setError(null);
    key.current ??= newIdempotencyKey();
    try {
      const result = await billingApi.checkout(key.current);
      const url = new URL(result.url);
      if (url.protocol !== "https:" || url.hostname !== "checkout.stripe.com")
        throw new Error("Checkout returned an unexpected address.");
      window.location.assign(url.href);
    } catch (err) {
      setError(friendlyError(err));
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeader title="Review credits">
        A one-time pack. No subscription. Stripe test payments only.
      </PageHeader>
      {query.loading ? (
        <Loading label="Loading review credits" />
      ) : !query.data ? (
        <ErrorState error={query.error} onRetry={query.reload} />
      ) : (
        <div className="max-w-3xl space-y-6">
          {!query.data.require_credits && (
            <Notice>Reviews are currently free. Purchasing test credits is optional.</Notice>
          )}
          {returned === "returned" && (
            <Notice>
              Checkout returned. Your balance updates only after a verified payment event arrives. A
              redirect alone does not add credits.
            </Notice>
          )}
          {returned === "cancelled" && (
            <Notice>Checkout was cancelled. No credits were added for this attempt.</Notice>
          )}
          {!!query.error && (
            <Notice tone="bad">
              The latest balance could not be refreshed.{" "}
              <button className="underline" onClick={query.reload}>
                Try again
              </button>
              .
            </Notice>
          )}
          <Card>
            <p className="text-sm text-muted">Available review credits</p>
            <p className="my-3 text-5xl font-medium">{query.data.credits}</p>
            <p className="text-sm text-muted">
              {query.data.require_credits
                ? "One new analysis uses one credit. A failed or cancelled analysis returns its credit. Reopening or exporting a report is free."
                : "Credits are not required while credit enforcement is disabled."}
            </p>
          </Card>
          <Card>
            <p className="text-sm text-accent">STRIPE TEST MODE</p>
            <h2 className="mt-3 text-2xl font-medium">
              {query.data.pack_credits} reviews ·{" "}
              {(query.data.pack_cents / 100).toLocaleString("en-US", {
                style: "currency",
                currency: query.data.currency,
              })}
            </h2>
            <p className="my-4 text-muted">
              This is a payment integration demonstration. Use Stripe’s published test payment
              details, never a real card. No recurring charge.
            </p>
            <Button disabled={!query.data.enabled} busy={busy} onClick={checkout}>
              Open Stripe test checkout
            </Button>
            <div className="mt-4" role="status">
              {error && <Notice tone="bad">{error}</Notice>}
            </div>
          </Card>
        </div>
      )}
    </>
  );
}
