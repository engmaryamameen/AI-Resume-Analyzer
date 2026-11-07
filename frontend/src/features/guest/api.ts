import { request } from "@/lib/http/client";

export const guestApi = {
  guestStatus: (signal?: AbortSignal) =>
    request<import("@/lib/types").GuestState>("/guest", { signal }),
  guestProgress: () =>
    request<import("@/lib/types").GuestState>("/guest/progress", { method: "POST" }),
  deleteGuest: () => request<void>("/guest", { method: "DELETE" }),
  guestAnalyze: (file: File, jobText: string, key: string) => {
    const form = new FormData();
    form.append("file", file);
    form.append("job_text", jobText);
    return request<import("@/lib/types").GuestState>("/guest/analyze", {
      method: "POST",
      body: form,
      headers: { "Idempotency-Key": key },
    });
  },
};
