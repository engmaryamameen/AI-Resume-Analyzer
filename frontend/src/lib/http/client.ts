import { validateResponse } from "../contracts";

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

function abortableDelay(ms: number, signal?: AbortSignal | null): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(signal.reason);
      return;
    }
    const abort = () => {
      clearTimeout(timer);
      signal?.removeEventListener("abort", abort);
      reject(signal?.reason);
    };
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", abort);
      resolve();
    }, ms);
    signal?.addEventListener("abort", abort, { once: true });
  });
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
    await abortableDelay(300 * 3 ** attempt, options.signal);
  }
  throw new Error("Request attempts exhausted");
}

export async function request<T>(
  path: string,
  init: RequestInit & { json?: unknown } = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  const method = (init.method ?? "GET").toUpperCase();
  if (method !== "GET") headers.set("X-CSRF-Token", csrfToken());
  let body = init.body;
  if (init.json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(init.json);
  }
  const controller = new AbortController();
  const abort = () => controller.abort(init.signal?.reason);
  if (init.signal?.aborted) abort();
  else init.signal?.addEventListener("abort", abort, { once: true });
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
  } catch (error) {
    if (init.signal?.aborted) {
      clearTimeout(timer);
      init.signal.removeEventListener("abort", abort);
      throw error;
    }
    if (controller.signal.aborted) {
      clearTimeout(timer);
      init.signal?.removeEventListener("abort", abort);
      throw new ApiError(
        0,
        "request_timeout",
        "The analysis service took too long to respond. Please try again.",
      );
    }
    clearTimeout(timer);
    init.signal?.removeEventListener("abort", abort);
    throw new ApiError(
      0,
      "network_error",
      "The analysis service is unavailable. Please try again shortly.",
    );
  }
  try {
    if (res.status === 204) return undefined as T;
    const isJson = res.headers.get("content-type")?.includes("json");
    let payload: unknown;
    try {
      payload = isJson ? await res.json() : await res.text();
    } catch (error) {
      if (init.signal?.aborted) throw error;
      throw new ApiError(
        res.status,
        controller.signal.aborted ? "request_timeout" : "invalid_response",
        "The service returned an unreadable response. Please try again.",
      );
    }
    if (!res.ok) {
      const envelope =
        payload && typeof payload === "object" && "error" in payload ? payload.error : null;
      const e =
        envelope && typeof envelope === "object" ? (envelope as Record<string, unknown>) : {};
      if (res.status === 401 && !STAYS_ON_PAGE.test(path)) leaveForLogin();
      throw new ApiError(
        res.status,
        typeof e.code === "string" ? e.code : "http_error",
        typeof e.message === "string" ? e.message : "Something went wrong.",
        typeof e.request_id === "string" ? e.request_id : res.headers.get("x-request-id"),
        e.details && typeof e.details === "object" && !Array.isArray(e.details)
          ? (e.details as Record<string, unknown>)
          : {},
      );
    }
    if (!isJson || !validateResponse(path, method, res.status, payload))
      throw new ApiError(
        res.status,
        "invalid_response",
        "The service returned an unexpected response. Please try again.",
      );
    return payload as T;
  } finally {
    clearTimeout(timer);
    init.signal?.removeEventListener("abort", abort);
  }
}
