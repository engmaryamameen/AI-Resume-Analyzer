import type { Metadata } from "next";
import { AuthForm } from "@/components/auth-form";
import { SiteHeader } from "@/components/site-header";

export const metadata: Metadata = { title: "Sign in" };

export default function Login() {
  return (<><SiteHeader /><main id="main" className="px-4"><AuthForm mode="login" /></main></>);
}
