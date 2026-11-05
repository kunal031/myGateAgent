"use client";

import React from "react";

/**
 * A titled panel and a label/value row -- the two shapes every stats
 * surface in this app is built from.
 *
 * These existed three times over: ProfileTabs and DeepPanels each had a
 * private `Card` and `Row`, and the admin pages were about to add a
 * fourth. The copies had already drifted (radius, padding, title size),
 * so the profile page and the analytics page rendered the same idea at
 * two different scales. One definition, two size variants.
 */

export function Panel({
  title,
  span = false,
  size = "md",
  action,
  children,
}: {
  title?: string;
  /** Spans both columns of a two-column grid. */
  span?: boolean;
  /** `sm` is the tighter analytics scale; `md` the profile scale. */
  size?: "sm" | "md";
  /** Optional control in the header, right-aligned. */
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  const sm = size === "sm";
  return (
    <section
      className={
        (sm ? "rounded-[var(--radius)] p-3 " : "rounded-[var(--radius-lg)] p-3.5 ")
        + (span ? "lg:col-span-2" : "")
      }
      style={{
        background: "var(--surface)",
        border: "var(--line-width) solid var(--line)",
      }}
    >
      {(title || action) && (
        <div className="mb-2 flex items-center justify-between gap-2">
          {title && (
            <h3
              className={
                "font-extrabold uppercase tracking-wider "
                + (sm ? "text-[11px]" : "text-[10px]")
              }
              style={{ color: "var(--ink-faint)" }}
            >
              {title}
            </h3>
          )}
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function Row({
  label,
  value,
  hint,
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
}) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1.5">
      <span className="min-w-0 text-[12px]" style={{ color: "var(--ink-soft)" }}>
        {label}
        {hint && (
          <span className="ml-1 text-[10px]" style={{ color: "var(--ink-faint)" }}>
            {hint}
          </span>
        )}
      </span>
      <span
        className="shrink-0 text-right text-[12px] font-bold"
        style={{ color: "var(--ink)" }}
      >
        {value}
      </span>
    </div>
  );
}
