"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { friendlyError } from "@/lib/copy";
import { Button, Card, Notice, TextField } from "./ui";

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const isRegister = mode === "register";

  async function submit(e: React.FormEvent) {
    e.preventDefault();
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
    <Card className="mx-auto mt-10 max-w-md">
      <h1 className="font-serif text-3xl">{isRegister ? "Create your account" : "Welcome back"}</h1>
      <form onSubmit={submit} className="mt-5 space-y-4" noValidate>
        <TextField label="Email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        <TextField label="Password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
          autoComplete={isRegister ? "new-password" : "current-password"}
          hint={isRegister ? "At least 12 characters. A few random words works well." : undefined} />
        {error && <Notice tone="bad">{error}</Notice>}
        <Button type="submit" busy={busy} className="w-full">{isRegister ? "Create account" : "Sign in"}</Button>
      </form>
      <p className="mt-4 text-sm text-muted">
        {isRegister ? <>Already have an account? <Link href="/login" className="text-accent underline">Sign in</Link></>
          : <>New here? <Link href="/register" className="text-accent underline">Create an account</Link></>}
      </p>
    </Card>
  );
}
