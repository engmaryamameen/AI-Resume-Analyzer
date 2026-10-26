"use client";

import { api } from "@/lib/api";
import { ORIGIN_LABEL } from "@/lib/copy";
import { useAsync } from "@/lib/hooks";
import type { ModelStatus } from "@/lib/types";
import { Badge, Card } from "./ui";

export function ModelStatusView({ status }: { status: ModelStatus }) {
  return (
    <Card as="section">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="font-serif text-xl">Analysis models on this server</h2>
        <Badge tone={status.learned_models_approved ? "good" : "warn"}>{status.learned_models_approved ? "Local models approved" : "Models not available"}</Badge>
      </div>
      <p className="mt-2 text-sm">{status.note}</p>
      {!status.learned_models_approved && (
        <p className="mt-2 text-sm text-muted">Analyses still work. They use the rule-based reading, which is more literal and says so on every result.</p>
      )}
      {status.models.length > 0 && (
        <ul className="mt-3 space-y-1 text-sm">
          {status.models.map((m) => <li key={m.id}><span className="font-medium capitalize">{m.id}</span>: {m.base_model} ({ORIGIN_LABEL[m.origin]}), {m.license}</li>)}
        </ul>
      )}
    </Card>
  );
}

/** Fetches and shows the model status; renders nothing if it can't be loaded (it is informational). */
export function ModelStatusPanel() {
  const status = useAsync(() => api.modelStatus(), []);
  if (!status.data) return null;
  return <ModelStatusView status={status.data} />;
}
