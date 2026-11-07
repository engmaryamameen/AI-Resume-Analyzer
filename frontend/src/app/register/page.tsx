import type { Metadata } from "next";
import { AuthForm } from "@/features/auth/components/auth-form";
import { SiteHeader } from "@/components/site-header";

export const metadata: Metadata = { title: "Create account" };

export default function Register() {
  return (
    <>
      <SiteHeader />
      <main id="main" className="px-4">
        <AuthForm mode="register" />
      </main>
    </>
  );
}
