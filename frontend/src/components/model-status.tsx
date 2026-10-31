"use client";

import { api } from "@/lib/api";
import { ORIGIN_LABEL } from "@/lib/copy";
import { useAsync } from "@/lib/hooks";
import type { ModelStatus } from "@/lib/types";
import { Badge, Card } from "./ui";

export function ModelStatusView({ status }: { status: ModelStatus }) {
  const semantic = status.available_method === "semantic";
  return (
    <Card as="section">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="font-serif text-xl">Reading method</h2>
        <Badge tone="plain">
          {semantic
            ? "Local semantic models"
            : status.learned_models_approved
              ? "Local models approved"
              : "Local rules"}
        </Badge>
      </div>
      <p className="mt-2 max-w-prose text-sm leading-7 text-muted">
        {semantic
          ? "Pretrained models on this server compare the meaning of requirements and résumé passages. Rules handle entities and dates. Each report records the method actually used."
          : status.learned_models_approved
            ? "Approved local models are configured on this server. Each report identifies the method that completed its review, including any fallback to local rules."
            : "This installation uses the local rule-based reader. It compares your wording and surrounding context with the role’s requirements, and may miss paraphrases."}
      </p>
      <p className="mt-2 text-sm text-muted">Your documents stay on this server.</p>
      <details className="mt-4 text-sm">
        <summary className="cursor-pointer text-accent">Setup information</summary>
        <p className="mt-3 leading-7 text-muted">{status.note}</p>
        {status.models.length > 0 && (
          <ul className="mt-3 space-y-2">
            {status.models.map((model) => (
              <li key={model.id} className="text-sm text-muted">
                <span className="font-medium text-ink">{model.base_model}</span>
                <span>
                  {" "}
                  · {ORIGIN_LABEL[model.origin]} · {model.license}
                </span>
              </li>
            ))}
          </ul>
        )}
      </details>
    </Card>
  );
}

export function ModelStatusPanel() {
  const status = useAsync(() => api.modelStatus(), []);
  return status.data ? <ModelStatusView status={status.data} /> : null;
}
