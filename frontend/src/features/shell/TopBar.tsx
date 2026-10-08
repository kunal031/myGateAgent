"use client";

import React from "react";
import { Menu, Zap } from "lucide-react";

import ThemeSwitcher from "../theme/ThemeSwitcher";

/** Mobile-only header. The sidebar carries branding from md: upward. */
export default function TopBar({ onMenu }: { onMenu: () => void }) {
  return (
    <header
      className="md:hidden sticky top-0 z-30 flex items-center justify-between gap-3 px-4 py-3"
      style={{
        background: "var(--surface)",
        borderBottom: "var(--line-width) solid var(--line)",
      }}
    >
      <button
        type="button"
        onClick={onMenu}
        aria-label="Open navigation"
        className="flex h-10 w-10 items-center justify-center rounded-[var(--radius)]"
        style={{ border: "var(--line-width) solid var(--line)", color: "var(--ink)" }}
      >
        <Menu className="h-5 w-5" />
      </button>

      <div className="flex items-center gap-2">
        <Zap className="h-4 w-4" style={{ color: "var(--ink)" }} />
        <span className="text-sm font-extrabold tracking-wide" style={{ color: "var(--ink)" }}>
          GATEMASTER
        </span>
      </div>

      <ThemeSwitcher compact />
    </header>
  );
}
