"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { authApi } from "../api";
import { friendlyError } from "@/lib/copy";
import { Button, Notice, TextField } from "@/components/ui";

type Mode = "forgot-password" | "reset-password" | "verify-email";
export function AccountLinkForm({ mode }: { mode: Mode }) {
  const [token, setToken] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    const token = new URLSearchParams(window.location.hash.slice(1)).get("token") ?? "";
    if (token) setToken(token);
    if (token)
      window.history.replaceState(null, "", window.location.pathname + window.location.search);
  }, []);
  const title =
    mode === "forgot-password"
      ? "Recover your account"
      : mode === "reset-password"
        ? "Choose a new password"
        : "Verify your email";
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      if (mode === "forgot-password") await authApi.forgotPassword(email);
      else if (mode === "reset-password") await authApi.resetPassword(token, password);
      else if (token) await authApi.verifyEmail(token, password);
      else await authApi.requestVerification(email);
      setDone(true);
    } catch (error) {
      setError(friendlyError(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="mx-auto max-w-md px-4 py-12">
      <h1 className="font-sans font-medium text-3xl">{title}</h1>
      {done ? (
        <div role="status" className="mt-5 space-y-4">
          <p>
            {mode === "forgot-password" || (mode === "verify-email" && !token)
              ? "If this address is eligible, an email will arrive with a link valid for 30 minutes. You can request another link if it does not arrive."
              : mode === "reset-password"
                ? "Your password has changed and all sessions have been signed out."
                : "Your email is verified. Sign in with the password you just chose."}
          </p>
          <Link className="text-accent underline" href="/login">
            Continue to sign in
          </Link>
        </div>
      ) : (
        <form onSubmit={submit} className="mt-5 space-y-4">
          {(mode === "forgot-password" || (mode === "verify-email" && !token)) && (
            <TextField
              label="Email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          )}
          {(mode === "reset-password" || (mode === "verify-email" && token)) && (
            <TextField
              label="New password"
              type="password"
              autoComplete="new-password"
              minLength={12}
              maxLength={256}
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          )}
          {mode === "reset-password" && !token && (
            <Notice tone="warn">
              Open the link in your recovery email.{" "}
              <Link href="/forgot-password">Request a new link</Link>.
            </Notice>
          )}
          {error && <Notice tone="bad">{error}</Notice>}
          <Button type="submit" busy={busy} disabled={mode === "reset-password" && !token}>
            {mode === "forgot-password" || (mode === "verify-email" && !token)
              ? "Send email link"
              : mode === "reset-password"
                ? "Reset password"
                : "Verify email"}
          </Button>
        </form>
      )}
    </section>
  );
}
