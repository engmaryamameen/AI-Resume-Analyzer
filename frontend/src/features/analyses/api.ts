import type { Analysis, AnalysisDetail, Comparison, Page } from "@/lib/types";
import { request } from "@/lib/http/client";

export const analysesApi = {
  analyses: (offset = 0, signal?: AbortSignal) =>
    request<Page<Analysis>>(`/analyses?limit=20&offset=${offset}`, { signal }),
  analysis: (id: string, signal?: AbortSignal) =>
    request<AnalysisDetail>(`/analyses/${id}`, { signal }),
  createAnalysis: (resume_version_id: string, jd_version_id: string, key: string) =>
    request<Analysis>("/analyses", {
      method: "POST",
      json: { resume_version_id, jd_version_id },
      headers: { "Idempotency-Key": key },
    }),
  cancelAnalysis: (id: string) => request<Analysis>(`/analyses/${id}/cancel`, { method: "POST" }),
  compare: (base: string, target: string, signal?: AbortSignal) =>
    request<Comparison>(`/analyses/compare?${new URLSearchParams({ base, target })}`, { signal }),
  reportUrl: (id: string, format: "json" | "md" | "csv") =>
    `/api/v1/analyses/${id}/report?format=${format}`,
};
