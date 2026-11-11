import type { Registration, User } from "@/lib/types";
import { request } from "@/lib/http/client";

export const authApi = {
  me: (signal?: AbortSignal) => request<User>("/auth/me", { signal }),
  register: (email: string, password: string) =>
    request<Registration>("/auth/register", { method: "POST", json: { email, password } }),
  login: (email: string, password: string) =>
    request<User>("/auth/login", { method: "POST", json: { email, password } }),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  deleteAccount: (password: string) =>
    request<void>("/auth/delete-account", { method: "POST", json: { password } }),
  forgotPassword: (email: string) =>
    request<void>("/auth/forgot-password", { method: "POST", json: { email } }),
  requestVerification: (email: string) =>
    request<void>("/auth/request-verification", { method: "POST", json: { email } }),
  verifyEmail: (token: string, password: string) =>
    request<void>("/auth/verify-email", { method: "POST", json: { token, password } }),
  resetPassword: (token: string, password: string) =>
    request<void>("/auth/reset-password", { method: "POST", json: { token, password } }),
  sessions: (signal?: AbortSignal) =>
    request<{ id: string; created_at: string; expires_at: string; current: boolean }[]>(
      "/auth/sessions",
      { signal },
    ),
  revokeSession: (id: string) =>
    request<void>(`/auth/sessions/${encodeURIComponent(id)}`, { method: "DELETE" }),
};
