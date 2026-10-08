"use client";

import React from "react";
import { Moon, Palette, Sun } from "lucide-react";

import { THEME_LABELS, THEMES, Theme, useTheme } from "./ThemeProvider";

const ICONS: Record<Theme, React.ComponentType<{ className?: string }>> = {
  synapse: Palette,
  light: Sun,
  dark: Moon,
};

export default function ThemeSwitcher({ compact = false }: { compact?: boolean }) {
  const { theme, setTheme } = useTheme();

  return (
    <div
      className="inline-flex items-center gap-1 p-1 rounded-[var(--radius-pill)]"
      style={{
        background: "var(--surface-sunk)",
        border: "var(--line-width) solid var(--line)",
      }}
      role="group"
      aria-label="Theme"
    >
      {THEMES.map((option) => {
        const Icon = ICONS[option];
        const active = theme === option;
        return (
          <button
            key={option}
            type="button"
            onClick={() => setTheme(option)}
            aria-pressed={active}
            title={THEME_LABELS[option]}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-[var(--radius-pill)] text-xs font-semibold transition-colors"
            style={{
              background: active ? "var(--accent)" : "transparent",
              color: active ? "var(--accent-ink)" : "var(--ink-faint)",
              border: active
                ? "var(--line-width) solid var(--line)"
                : "var(--line-width) solid transparent",
            }}
          >
            <Icon className="w-3.5 h-3.5" />
            {!compact && <span>{THEME_LABELS[option]}</span>}
          </button>
        );
      })}
    </div>
  );
}
