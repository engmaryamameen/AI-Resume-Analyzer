import { request } from "@/lib/http/client";
export type BillingStatus = {
  enabled: boolean;
  require_credits?: boolean;
  test_mode: boolean;
  credits: number;
  pack_credits: number;
  pack_cents: number;
  currency: string;
};
export const billingApi = {
  status: (signal?: AbortSignal) => request<BillingStatus>("/billing", { signal }),
  checkout: (key: string) =>
    request<{ url: string }>("/billing/checkout", {
      method: "POST",
      headers: { "Idempotency-Key": key },
    }),
};
