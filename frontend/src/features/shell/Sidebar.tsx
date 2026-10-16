"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { X, Zap } from "lucide-react";

import ThemeSwitcher from "../theme/ThemeSwitcher";
import { NAV_ITEMS, isActivePath } from "./nav-items";

interface SidebarProps {
  /** Drawer state, used on mobile only. */
  open?: boolean;
  onClose?: () => void;
}

export default function Sidebar({ open = false, onClose }: SidebarProps) {
  const pathname = usePathname();

  return (
    <>
      {/* Scrim: only present while the mobile drawer is open. */}
      {open && (
        <button
          type="button"
          aria-label="Close navigation"
          onClick={onClose}
          className="md:hidden fixed inset-0 z-40 bg-black/40"
        />
      )}

      <aside
        // invisible + pointer-events-none keeps the closed drawer out of the
        // layout and the tab order on mobile; md: restores it permanently.
        className={`fixed left-0 top-0 z-50 flex h-dvh w-64 flex-col transition-transform duration-200 md:visible md:translate-x-0 md:pointer-events-auto ${
          open
            ? "visible translate-x-0"
            : "invisible -translate-x-full pointer-events-none"
        }`}
        style={{
          background: "var(--surface)",
          borderRight: "var(--line-width) solid var(--line)",
        }}
      >
        <div
          className="flex items-center justify-between gap-3 p-4"
          style={{ borderBottom: "var(--line-width) solid var(--line)" }}
        >
          <div className="flex items-center gap-2.5">
            <div
              className="flex h-9 w-9 items-center justify-center rounded-[var(--radius)]"
              style={{
                background: "var(--accent)",
                border: "var(--line-width) solid var(--line)",
                boxShadow: "var(--shadow-sm)",
              }}
            >
              <Zap className="h-4 w-4" style={{ color: "var(--accent-ink)" }} />
            </div>
            <div>
              <div className="text-sm font-extrabold tracking-wide" style={{ color: "var(--ink)" }}>
                GATEMASTER
              </div>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Close navigation"
            className="md:hidden flex h-9 w-9 items-center justify-center rounded-[var(--radius-pill)]"
            style={{ border: "var(--line-width) solid var(--line)", color: "var(--ink)" }}
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <nav className="flex-1 space-y-1.5 overflow-y-auto p-3">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const active = isActivePath(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onClose}
                aria-current={active ? "page" : undefined}
                className="flex min-h-11 items-center justify-between rounded-[var(--radius)] px-3 py-2.5 text-sm font-semibold transition-colors"
                style={{
                  background: active ? "var(--accent)" : "transparent",
                  color: active ? "var(--accent-ink)" : "var(--ink-soft)",
                  border: active
                    ? "var(--line-width) solid var(--line)"
                    : "var(--line-width) solid transparent",
                  boxShadow: active ? "var(--shadow-sm)" : "none",
                }}
              >
                <span className="flex items-center gap-2.5">
                  <Icon className="h-4 w-4" />
                  {item.name}
                </span>
                <span
                  className="rounded-[var(--radius-pill)] px-1.5 py-0.5 text-[10px] font-bold"
                  style={{
                    background: active ? "var(--surface)" : "var(--surface-sunk)",
                    color: "var(--ink-faint)",
                  }}
                >
                  {item.tag}
                </span>
              </Link>
            );
          })}
        </nav>

        <div className="p-3">
          <ThemeSwitcher />
        </div>
      </aside>
    </>
  );
}
