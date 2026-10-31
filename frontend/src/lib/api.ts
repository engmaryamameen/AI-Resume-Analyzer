import type {
  Analysis,
  AnalysisDetail,
  Comparison,
  DemoResult,
  DemoSamples,
  Job,
  JobDetail,
  ModelStatus,
  Page,
  Resume,
  ResumeDetail,
  ResumeVersion,
  User,
} from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public requestId: string | null = null,
    public details: Record<string, unknown> = {},
  ) {
    super(message);
  }
}

function csrfToken(): string {
  if (typeof document === "undefined") return "";
  const hit = document.cookie.split("; ").find((c) => c.startsWith("rs_csrf="));
  return hit ? decodeURIComponent(hit.split("=")[1] ?? "") : "";
}

export function newIdempotencyKey(): string {
  return crypto.randomUUID();
}

// Wrong credentials on these routes are a 401 that belongs on the form, not a reason to leave the page.
const STAYS_ON_PAGE = /^\/auth\/(login|register)$/;

function leaveForLogin(): void {
  if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login"))
    window.location.assign("/login");
}

async function fetchWithReadRetry(url: string, options: RequestInit): Promise<Response> {
  const attempts = options.method === "GET" ? 3 : 1;
  for (let attempt = 0; attempt < attempts; attempt++) {
    try {
      const response = await fetch(url, options);
      if (attempt + 1 === attempts || ![502, 503, 504].includes(response.status)) return response;
      await response.body?.cancel();
    } catch (error) {
      if (options.signal?.aborted || attempt + 1 === attempts) throw error;
    }
    await new Promise((resolve) => setTimeout(resolve, 300 * 3 ** attempt));
  }
  throw new Error("Request attempts exhausted");
}

async function request<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const method = (init.method ?? "GET").toUpperCase();
  if (method !== "GET") headers.set("X-CSRF-Token", csrfToken());
  let body = init.body;
  if (init.json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(init.json);
  }
  const controller = new AbortController();
  const timeoutMs = path.startsWith("/demo/") ? 12000 : 30000;
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let res: Response;
  try {
    res = await fetchWithReadRetry(`/api/v1${path}`, {
      ...init,
      method,
      headers,
      body,
      credentials: "same-origin",
      signal: controller.signal,
    });
  } catch {
    if (controller.signal.aborted) {
      throw new ApiError(
        0,
        "request_timeout",
        "The analysis service took too long to respond. Please try again.",
      );
    }
    throw new ApiError(
      0,
      "network_error",
      "The analysis service is unavailable. Please try again shortly.",
    );
  } finally {
    clearTimeout(timer);
  }
  if (res.status === 204) return undefined as T;
  const isJson = res.headers.get("content-type")?.includes("json");
  const payload = isJson ? await res.json() : await res.text();
  if (!res.ok) {
    const e = (
      payload as {
        error?: {
          code: string;
          message: string;
          request_id?: string;
          details?: Record<string, unknown>;
        };
      }
    )?.error;
    if (res.status === 401 && !STAYS_ON_PAGE.test(path)) leaveForLogin();
    throw new ApiError(
      res.status,
      e?.code ?? "http_error",
      e?.message ?? "Something went wrong.",
      e?.request_id ?? res.headers.get("x-request-id"),
      e?.details ?? {},
    );
  }
  return payload as T;
}

export interface RequirementEdit {
  id?: string;
  text: string;
  kind: string;
  category: string;
  min_years?: number | null;
}

export const api = {
  guestStatus: () => request<import("./types").GuestState>("/guest"),
  guestProgress: () => request<import("./types").GuestState>("/guest/progress", { method: "POST" }),
  deleteGuest: () => request<void>("/guest", { method: "DELETE" }),
  guestAnalyze: (file: File, jobText: string, key: string) => {
    const form = new FormData();
    form.append("file", file);
    form.append("job_text", jobText);
    return request<import("./types").GuestState>("/guest/analyze", {
      method: "POST",
      body: form,
      headers: { "Idempotency-Key": key },
    });
  },
  me: () => request<User>("/auth/me"),
  register: (email: string, password: string) =>
    request<User>("/auth/register", { method: "POST", json: { email, password } }),
  login: (email: string, password: string) =>
    request<User>("/auth/login", { method: "POST", json: { email, password } }),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  deleteAccount: (password: string) =>
    request<void>("/auth/delete-account", { method: "POST", json: { password } }),

  modelStatus: () => request<ModelStatus>("/system/models"),

  resumes: (offset = 0) => request<Page<Resume>>(`/resumes?limit=20&offset=${offset}`),
  resume: (id: string, version?: number) =>
    request<ResumeDetail>(`/resumes/${id}${version ? `?version=${version}` : ""}`),
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

  jobs: (offset = 0) => request<Page<Job>>(`/job-descriptions?limit=20&offset=${offset}`),
  job: (id: string, version?: number) =>
    request<JobDetail>(`/job-descriptions/${id}${version ? `?version=${version}` : ""}`),
  createJob: (title: string, text: string) =>
    request<JobDetail>("/job-descriptions", { method: "POST", json: { title, text } }),
  saveRequirements: (id: string, base_version_no: number, requirements: RequirementEdit[]) =>
    request<JobDetail>(`/job-descriptions/${id}/requirements`, {
      method: "PUT",
      json: { base_version_no, requirements },
    }),
  deleteJob: (id: string) => request<void>(`/job-descriptions/${id}`, { method: "DELETE" }),

  analyses: (offset = 0) => request<Page<Analysis>>(`/analyses?limit=20&offset=${offset}`),
  analysis: (id: string) => request<AnalysisDetail>(`/analyses/${id}`),
  createAnalysis: (resume_version_id: string, jd_version_id: string, key: string) =>
    request<Analysis>("/analyses", {
      method: "POST",
      json: { resume_version_id, jd_version_id },
      headers: { "Idempotency-Key": key },
    }),
  cancelAnalysis: (id: string) => request<Analysis>(`/analyses/${id}/cancel`, { method: "POST" }),
  compare: (base: string, target: string) =>
    request<Comparison>(`/analyses/compare?base=${base}&target=${target}`),
  reportUrl: (id: string, format: "json" | "md" | "csv") =>
    `/api/v1/analyses/${id}/report?format=${format}`,

  demoSamples: () => request<DemoSamples>("/demo/samples"),
  demoAnalyze: (body: { resume_id: string; job_id?: string; job_text?: string }) =>
    request<DemoResult>("/demo/analyze", { method: "POST", json: body }),
};
