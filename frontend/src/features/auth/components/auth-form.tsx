"use client";

import Link from "next/link";
import { useAuthForm } from "../use-auth-form";
import { Icon } from "@/components/icon";
import { Button, Notice, TextField } from "@/components/ui";

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const {
    email,
    setEmail,
    password,
    setPassword,
    error,
    busy,
    showPassword,
    setShowPassword,
    fields,
    isRegister,
    submit,
  } = useAuthForm(mode);

  return (
    <div className="auth-layout">
      <aside className="auth-story">
        <span className="micro-label">RÉSUMÉ WORKSPACE</span>
        <h2>
          Your experience.
          <br />
          Keep the context.
        </h2>
        <p>
          Keep your résumés, target roles, and thoughtful revisions in one place. Pick up wherever
          you left off.
        </p>
        <div className="auth-annotation">
          <span className="auth-annotation-number">EXAMPLE RÉSUMÉ PASSAGE</span>
          <blockquote>
            “Built internal services in Python and FastAPI for billing operations.”
          </blockquote>
          <div>
            <Icon name="check" size={15} /> Experience in context
          </div>
        </div>
        <div className="auth-privacy">
          <Icon name="shield" size={20} />
          <span>
            Your documents stay on this server.
            <br />
            No outside AI services. No advertising trackers.
          </span>
        </div>
      </aside>
      <section className="auth-form-panel">
        <h1 className="font-sans font-medium text-3xl mt-5">
          {isRegister ? "Create your account" : "Welcome back"}
        </h1>
        <p className="mt-3 text-sm leading-6 text-muted">
          {isRegister
            ? "Save your documents, keep versions, and compare your reviews."
            : "Pick up where you left off. Your documents and findings are waiting."}
        </p>
        <form onSubmit={submit} className="mt-5 space-y-4" noValidate>
          <TextField
            label="Email"
            error={fields.email}
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <TextField
            label="Password"
            error={fields.password}
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
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={isRegister ? "new-password" : "current-password"}
            hint={isRegister ? "At least 12 characters. A few random words works well." : undefined}
          />
          {error && <Notice tone="bad">{error}</Notice>}
          <Button type="submit" busy={busy} className="w-full">
            {isRegister ? "Create account" : "Sign in"}
          </Button>
        </form>
        {!isRegister && (
          <p className="mt-4 text-sm">
            <Link href="/forgot-password" className="text-accent underline">
              Forgot your password?
            </Link>
          </p>
        )}
        <p className="auth-guest-link">
          <Icon name="document" size={16} />
          <Link href="/#analyze">Try one résumé analysis without an account</Link>
        </p>
        <p className="mt-4 text-sm text-muted">
          {isRegister ? (
            <>
              Already have an account?{" "}
              <Link href="/login" className="text-accent underline">
                Sign in
              </Link>
            </>
          ) : (
            <>
              New here?{" "}
              <Link href="/register" className="text-accent underline">
                Create an account
              </Link>
            </>
          )}
        </p>
      </section>
    </div>
  );
}
