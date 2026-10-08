"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { NAV_ITEMS, isActivePath } from "./nav-items";

/** Mobile-only tab bar. Hidden from md: upward, where the sidebar takes over. */
export default function BottomNav() {
  const pathname = usePathname();
  const items = NAV_ITEMS.filter((item) => item.primary);

  return (
    <nav
      className="md:hidden fixed bottom-0 inset-x-0 z-40 grid"
      style={{
        gridTemplateColumns: `repeat(${items.length}, minmax(0, 1fr))`,
        background: "var(--surface)",
        borderTop: "var(--line-width) solid var(--line)",
        // Keeps the bar clear of the iOS home indicator.
        paddingBottom: "env(safe-area-inset-bottom)",
      }}
    >
      {items.map((item) => {
        const Icon = item.icon;
        const active = isActivePath(pathname, item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            // min-h-14 keeps every target above the 44px touch minimum.
            className="flex flex-col items-center justify-center gap-0.5 min-h-14 py-2 text-[11px] font-semibold"
            style={{ color: active ? "var(--accent-ink)" : "var(--ink-faint)" }}
          >
            <span
              className="flex items-center justify-center w-9 h-7 rounded-[var(--radius-pill)]"
              style={{
                background: active ? "var(--accent)" : "transparent",
                border: active
                  ? "var(--line-width) solid var(--line)"
                  : "var(--line-width) solid transparent",
              }}
            >
              <Icon className="w-4 h-4" />
            </span>
            {item.name}
          </Link>
        );
      })}
    </nav>
  );
}
