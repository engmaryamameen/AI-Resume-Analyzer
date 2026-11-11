"use client";

import { useEffect, useId, useRef, useState } from "react";
import Link from "next/link";
import { Icon } from "@/components/icon";
import { BRAND } from "@/lib/brand";
import styles from "./brand.module.css";

export function Brand() {
  return (
    <Link href="/" className="brand-lockup" aria-label={`${BRAND.name} home`}>
      <span className={styles.wordmark}>{BRAND.wordmark}</span>
    </Link>
  );
}
export function SiteHeader() {
  const [open, setOpen] = useState(false);
  const navId = useId();
  const drawer = useRef<HTMLDialogElement>(null);
  const [mobile, setMobile] = useState(false);
  useEffect(() => {
    const query = window.matchMedia("(max-width: 1000px)");
    const update = () => {
      setMobile(query.matches);
      setOpen(false);
    };
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  useEffect(() => {
    if (!mobile || !open) {
      drawer.current?.close();
      return;
    }
    drawer.current?.showModal();
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [mobile, open]);
  const header = useRef<HTMLElement>(null);
  const toggle = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    function closeOutside(event: PointerEvent) {
      if (header.current && !header.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function escape(event: KeyboardEvent) {
      if (event.key !== "Escape" || !header.current?.contains(document.activeElement)) return;
      if (open) {
        event.preventDefault();
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
  }
  const navigation = (
    <nav
      id={navId}
      aria-label="Main"
      className="site-nav"
      onClick={(event) => {
        if ((event.target as Element).closest("a")) close();
      }}
    >
      <Link href="/#how-it-works">How it works</Link>
      <Link href="/demo">Sample report</Link>
      <Link href="/#pricing">Pricing</Link>
      <Link href="/privacy">Privacy</Link>
      <span className="site-nav-divider" aria-hidden="true" />
      <Link href="/login">Sign in</Link>
      {mobile && (
        <Link href="/#analyze" className="site-nav-cta">
          Try the analyzer <Icon name="arrow" size={15} />
        </Link>
      )}
    </nav>
  );
  return (
    <header ref={header} className="site-topbar" data-menu-open={open || undefined}>
      <div className="site-topbar-inner">
        <Brand />
        <button
          ref={toggle}
          type="button"
          className="site-menu-toggle"
          aria-label="Open navigation"
          aria-expanded={open}
          aria-controls={navId}
          onClick={() => setOpen(!open)}
        >
          <Icon name="menu" size={21} />
        </button>
        {mobile ? (
          <dialog
            ref={drawer}
            className="site-mobile-drawer"
            aria-label="Navigation"
            onCancel={() => setOpen(false)}
            onClose={() => {
              setOpen(false);
              toggle.current?.focus();
            }}
            onClick={(event) => {
              if (event.target === event.currentTarget) close();
            }}
          >
            <div className="site-drawer-content">
              <div
                className="site-drawer-heading"
                onClick={(event) => {
                  if ((event.target as Element).closest("a")) close();
                }}
              >
                <Brand />
                <button
                  type="button"
                  className="site-menu-toggle"
                  aria-label="Close navigation"
                  aria-expanded={open}
                  onClick={close}
                >
                  <Icon name="x" size={20} />
                </button>
              </div>
              <p className="site-drawer-label">NAVIGATION</p>
              {navigation}
              <p className="site-drawer-note">
                <Icon name="shield" size={16} /> Résumé feedback, with evidence.
              </p>
            </div>
          </dialog>
        ) : (
          <>
            {navigation}
            <Link href="/#analyze" className="site-nav-cta site-header-cta">
              Try the analyzer <Icon name="arrow" size={15} />
            </Link>
          </>
        )}
      </div>
    </header>
  );
}
export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="site-footer-inner">
        <Brand />
        <p>Résumé review, with context.</p>
        <div className="footer-links">
          <Link href="/demo">View example</Link>
          <Link href="/privacy">Privacy &amp; data</Link>
        </div>
      </div>
    </footer>
  );
}
