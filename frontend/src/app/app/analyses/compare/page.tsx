"use client";

import Link from "next/link";
import { Icon } from "@/components/icon";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { ComparisonView } from "@/components/comparison-view";
import { ErrorState, Loading, Notice, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";

function Compare() {
  const q = useSearchParams();
  const base = q.get("base") ?? "";
  const target = q.get("target") ?? "";
  const cmp = useAsync(
    () => (base && target ? api.compare(base, target) : Promise.resolve(null)),
    [base, target],
  );

  if (!base || !target)
    return (
      <>
        <PageHeader title="Compare reviews">
          See how the evidence changes between two completed analyses.
        </PageHeader>
        <Notice tone="info">
          Choose two finished analyses from{" "}
          <Link href="/app/analyses" className="underline">
            Review history
          </Link>{" "}
          to compare them.
        </Notice>
      </>
    );
  if (cmp.loading) return <Loading />;
  if (cmp.error || !cmp.data) return <ErrorState error={cmp.error} onRetry={cmp.reload} />;
  return (
    <>
      <PageHeader title="What changed">
        Compare the recorded requirements and evidence from these two reviews.
      </PageHeader>
      <p className="mb-4">
        <Link href="/app/analyses" className="back-link text-accent underline">
          <Icon name="arrowLeft" size={16} /> Back to history
        </Link>
      </p>
      <ComparisonView c={cmp.data} />
    </>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<Loading />}>
      <Compare />
    </Suspense>
  );
}
