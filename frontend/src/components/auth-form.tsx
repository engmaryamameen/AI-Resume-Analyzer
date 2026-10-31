"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { friendlyError } from "@/lib/copy";
import { Icon } from "./icon";
import { Button, Notice, TextField } from "./ui";

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [fields, setFields] = useState<{ email?: string; password?: string }>({});
  const isRegister = mode === "register";

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const invalid = {
      email: /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())
        ? undefined
        : "Enter a valid email address.",
      password: !password
        ? "Enter your password."
        : isRegister && password.length < 12
          ? "Use at least 12 characters."
          : undefined,
    };
    setFields(invalid);
    if (invalid.email || invalid.password) return;
    setBusy(true);
    setError(null);
    try {
      await (isRegister ? api.register : api.login)(email, password);
      router.push("/app");
    } catch (err) {
      setError(friendlyError(err));
      setBusy(false);
    }
  }

  return (
    <div className="auth-layout">
      <aside className="auth-story">
        <span className="micro-label">MAKE ROOM FOR YOUR NEXT MOVE</span>
        <h2>
          Your experience.
          <br />A little more <em>direction.</em>
        </h2>
        <p>
          Keep your résumés, target roles, and thoughtful revisions in one place. Pick up wherever
          you left off.
        </p>
        <div className="auth-annotation">
          <span className="auth-annotation-number">A CLOSER READING</span>
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
        <span className="micro-label">YOUR PRIVATE WORKSPACE</span>
        <h1 className="font-serif text-3xl mt-5">
          {isRegister ? "Create your account" : "Welcome back"}
        </h1>
        <p className="mt-3 text-sm leading-6 text-muted">
          {isRegister
            ? "Make room for your experience. Start with an email and a password."
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
