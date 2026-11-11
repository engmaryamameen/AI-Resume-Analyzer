"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { authApi } from "./api";
import { friendlyError } from "@/lib/copy";
export function useAuthForm(mode: "login" | "register") {
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
    if (busy) return;
    const invalid = {
      email: /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())
        ? undefined
        : "Enter a valid email address.",
      password: !password
        ? "Enter your password."
        : isRegister && password.length < 8
          ? "Use at least 8 characters."
          : undefined,
    };
    setFields(invalid);
    if (invalid.email || invalid.password) return;
    setBusy(true);
    setError(null);
    try {
      if (isRegister) {
        const result = await authApi.register(email, password);
        router.push(result.email_verification_required ? "/verify-email" : "/app");
      } else {
        const user = await authApi.login(email, password);
        router.push(
          user.email_verification_required && !user.email_verified_at ? "/verify-email" : "/app",
        );
      }
    } catch (err) {
      setError(friendlyError(err));
      setBusy(false);
    }
  }

  return {
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
  };
}
