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
      // w-full + flex-1 children rather than inline-flex: in the 256px
      // sidebar three labelled buttons ("Original", "Light", "Dark")
      // overflowed the rail. Sharing the width equally keeps them inside
      // it and keeps the three hit targets the same size.
      className="flex w-full items-center gap-1 p-1 rounded-[var(--radius-pill)]"
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
            className={
              "flex items-center justify-center gap-1.5 rounded-[var(--radius-pill)] "
              + "py-1.5 text-xs font-semibold transition-colors "
              + (compact ? "px-2.5" : "min-w-0 flex-1 px-2")
            }
            style={{
              background: active ? "var(--accent)" : "transparent",
              color: active ? "var(--accent-ink)" : "var(--ink-faint)",
              border: active
                ? "var(--line-width) solid var(--line)"
                : "var(--line-width) solid transparent",
            }}
          >
            <Icon className="w-3.5 h-3.5" />
            {!compact && (
              <span className="truncate">{THEME_LABELS[option]}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}
