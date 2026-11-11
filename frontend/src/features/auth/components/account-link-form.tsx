"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Icon } from "@/components/icon";
import { authApi } from "../api";
import { friendlyError } from "@/lib/copy";
import { Button, Notice, TextField } from "@/components/ui";

type Mode = "forgot-password" | "reset-password" | "verify-email";
export function AccountLinkForm({ mode }: { mode: Mode }) {
  const [token, setToken] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
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
    if (token && mode !== "forgot-password" && password.length < 8) {
      setError("Use at least 8 characters.");
      return;
    }
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
    <section className="account-link-layout">
      <div className="account-link-card">
        <Link href="/" className="account-link-brand">
          Rolemaker
        </Link>
        <h1>{done && mode === "forgot-password" ? "Check your inbox" : title}</h1>
        {!done && (
          <p className="account-link-description">
            {mode === "forgot-password"
              ? "Enter the email you used to create your account. We’ll help you get back to your workspace."
              : mode === "reset-password"
                ? "Choose a password you haven’t used here before."
                : "Confirm your email to secure your workspace."}
          </p>
        )}
        {done ? (
          <div role="status" className="mt-5 space-y-4">
            <p>
              {mode === "forgot-password"
                ? `A password reset link has been requested for ${email}. Check your inbox and spam folder. The link expires after 30 minutes.`
                : mode === "verify-email" && !token
                  ? "If this address needs verification, an email will arrive with a link valid for 30 minutes."
                  : mode === "reset-password"
                    ? "Your password has changed and all sessions have been signed out."
                    : "Your email is verified. Sign in with the password you just chose."}
            </p>
            {mode === "forgot-password" && (
              <Button variant="secondary" onClick={() => setDone(false)}>
                Try again or use another email
              </Button>
            )}
            <Link className="account-link-back" href="/login">
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
                type={showPassword ? "text" : "password"}
                trailingAction={
                  <button
                    type="button"
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    aria-pressed={showPassword}
                    onClick={() => setShowPassword(!showPassword)}
                  >
                    <Icon name={showPassword ? "eyeOff" : "eye"} size={19} />
                  </button>
                }
                autoComplete="new-password"
                hint="At least 8 characters. You can also use a longer passphrase."
                minLength={8}
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
            <Button
              className="w-full"
              type="submit"
              busy={busy}
              disabled={mode === "reset-password" && !token}
            >
              {mode === "forgot-password" || (mode === "verify-email" && !token)
                ? "Send email link"
                : mode === "reset-password"
                  ? "Reset password"
                  : "Verify email"}
            </Button>
          </form>
        )}
        {!done && (
          <p className="account-link-footer">
            <Link href="/login">Back to sign in</Link>
            <span>
              New to Rolemaker? <Link href="/register">Create an account</Link>
            </span>
          </p>
        )}
      </div>
    </section>
  );
}
