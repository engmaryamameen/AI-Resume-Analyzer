import type { Job, JobDetail, Page } from "@/lib/types";
import { request } from "@/lib/http/client";
export interface RequirementEdit {
  id?: string;
  text: string;
  kind: string;
  category: string;
  min_years?: number | null;
}

export const jobDescriptionsApi = {
  jobs: (offset = 0, signal?: AbortSignal) =>
    request<Page<Job>>(`/job-descriptions?limit=20&offset=${offset}`, { signal }),
  job: (id: string, version?: number, signal?: AbortSignal) =>
    request<JobDetail>(`/job-descriptions/${id}${version ? `?version=${version}` : ""}`, {
      signal,
    }),
  createJob: (title: string, text: string) =>
    request<JobDetail>("/job-descriptions", { method: "POST", json: { title, text } }),
  saveRequirements: (id: string, base_version_no: number, requirements: RequirementEdit[]) =>
    request<JobDetail>(`/job-descriptions/${id}/requirements`, {
      method: "PUT",
      json: { base_version_no, requirements },
    }),
  deleteJob: (id: string) => request<void>(`/job-descriptions/${id}`, { method: "DELETE" }),
};
