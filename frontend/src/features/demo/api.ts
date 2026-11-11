import type { DemoResult, DemoSamples } from "@/lib/types";
import { request } from "@/lib/http/client";

export const demoApi = {
  demoSamples: (signal?: AbortSignal) => request<DemoSamples>("/demo/samples", { signal }),
  demoAnalyze: (body: { resume_id: string; job_id?: string; job_text?: string }) =>
    request<DemoResult>("/demo/analyze", { method: "POST", json: body }),
};
