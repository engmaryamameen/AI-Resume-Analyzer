import type { Page, Resume, ResumeDetail, ResumeVersion } from "@/lib/types";
import { request } from "@/lib/http/client";

export const resumesApi = {
  resumes: (offset = 0, signal?: AbortSignal) =>
    request<Page<Resume>>(`/resumes?limit=20&offset=${offset}`, { signal }),
  resume: (id: string, version?: number, signal?: AbortSignal) =>
    request<ResumeDetail>(`/resumes/${id}${version ? `?version=${version}` : ""}`, { signal }),
  uploadResume: (file: File, key: string) => {
    const form = new FormData();
    form.append("file", file);
    return request<Resume>("/resumes", {
      method: "POST",
      body: form,
      headers: { "Idempotency-Key": key },
    });
  },
  correctResume: (
    id: string,
    body: {
      base_version_no: number;
      block_edits?: Record<string, string>;
      contact?: { name?: string | null; email?: string | null; phone?: string | null };
    },
  ) => request<ResumeVersion>(`/resumes/${id}/corrections`, { method: "PUT", json: body }),
  deleteResume: (id: string) => request<void>(`/resumes/${id}`, { method: "DELETE" }),
};
