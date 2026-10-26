import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Margin Notes – résumé feedback grounded in evidence", template: "%s · Margin Notes" },
  description: "See which parts of a job description your résumé actually backs up, and what's missing, without inventing anything.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <a href="#main" className="skip-link">Skip to content</a>
        {children}
      </body>
    </html>
  );
}
