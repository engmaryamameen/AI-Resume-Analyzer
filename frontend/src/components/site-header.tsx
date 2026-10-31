"use client";

import { useEffect, useId, useRef, useState } from "react";
import Link from "next/link";
import { Icon } from "@/components/icon";
import { BRAND } from "@/lib/brand";

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <Link href="/" className="brand-lockup" aria-label={`${BRAND.name} home`}>
      <svg
        className="brand-mark"
        width="35"
        height="35"
        viewBox="0 0 36 36"
        fill="none"
        aria-hidden="true"
        focusable="false"
      >
        <rect width="36" height="36" rx="11" fill="currentColor" />
        <path
          d="M11 26V10h7a5 5 0 0 1 0 10h-7m7 0 7 6"
          stroke="#f8faff"
          strokeWidth="2.3"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d="m23 9 2 2 4-4"
          stroke="#cbd9ff"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      {!compact && (
        <span className="brand-wordmark">
          {BRAND.wordmark}
          <span className="brand-period">.</span>
        </span>
      )}
    </Link>
  );
}
export function SiteHeader() {
  const [open, setOpen] = useState(false);
  const navId = useId();
  const header = useRef<HTMLElement>(null);
  const toggle = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    function closeOutside(event: PointerEvent) {
      if (header.current && !header.current.contains(event.target as Node)) {
        setOpen(false);
        header.current
          .querySelectorAll("details[open]")
          .forEach((item) => item.removeAttribute("open"));
      }
    }
    function escape(event: KeyboardEvent) {
      if (event.key !== "Escape" || !header.current?.contains(document.activeElement)) return;
      const disclosure = header.current.querySelector<HTMLDetailsElement>("details[open]");
      if (disclosure) {
        disclosure.open = false;
        disclosure.querySelector("summary")?.focus();
      } else if (open) {
        setOpen(false);
        toggle.current?.focus();
      }
    }
    document.addEventListener("pointerdown", closeOutside);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("pointerdown", closeOutside);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);
  function close() {
    setOpen(false);
    header.current
      ?.querySelectorAll("details[open]")
      .forEach((item) => item.removeAttribute("open"));
  }
  return (
    <header ref={header} className="site-topbar" data-menu-open={open || undefined}>
      <div className="site-topbar-inner">
        <Brand />
        <button
          ref={toggle}
          type="button"
          className="site-menu-toggle"
          aria-label={open ? "Close navigation" : "Open navigation"}
          aria-expanded={open}
          aria-controls={navId}
          onClick={() => setOpen(!open)}
        >
          <Icon name={open ? "x" : "menu"} size={21} />
        </button>
        <nav
          id={navId}
          aria-label="Main"
          className="site-nav"
          onClick={(event) => {
            if ((event.target as Element).closest("a")) close();
          }}
        >
          <Link href="/" className="site-nav-home">
            Home
          </Link>
          <details className="site-nav-dropdown">
            <summary>
              Explore <Icon name="chevronDown" size={14} />
            </summary>
            <div className="site-dropdown-panel">
              <Link href="/#how-it-works">
                <Icon name="list" size={18} />
                <span>
                  How it works<small>From résumé to your next useful edit</small>
                </span>
              </Link>
              <Link href="/demo">
                <Icon name="grid" size={18} />
                <span>
                  View example<small>Explore a complete sample review</small>
                </span>
              </Link>
              <Link href="/privacy">
                <Icon name="shield" size={18} />
                <span>
                  Privacy<small>Understand how your data is handled</small>
                </span>
              </Link>
            </div>
          </details>
          <span className="site-nav-divider" aria-hidden="true" />
          <Link href="/login">Sign in</Link>
          <Link href="/#analyze" className="site-nav-cta">
            Try it free <Icon name="arrowUpRight" size={16} />
          </Link>
        </nav>
      </div>
    </header>
  );
}
export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="site-footer-inner">
        <Brand />
        <p>A closer reading. A clearer next step.</p>
        <div className="footer-links">
          <Link href="/demo">View example</Link>
          <Link href="/privacy">Privacy &amp; data</Link>
        </div>
      </div>
    </footer>
  );
}
