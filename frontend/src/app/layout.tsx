import { headers } from "next/headers";
import type { Metadata } from "next";
import "./globals.css";
import "./rolemark.css";
import { BRAND } from "@/lib/brand";

export const metadata: Metadata = {
  title: { default: `${BRAND.name} · Your next move, in focus`, template: `%s · ${BRAND.name}` },
  description: BRAND.description,
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  await headers(); // Request-specific CSP nonces require dynamic rendering.
  return (
    <html lang="en">
      <body>
        <a href="#main" className="skip-link">
          Skip to content
        </a>
        {children}
      </body>
    </html>
  );
}
