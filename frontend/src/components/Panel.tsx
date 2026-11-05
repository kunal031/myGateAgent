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
  hintOn = "label",
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
  /** Which side the hint annotates. The two pages that predate this
   *  component disagreed: the profile page qualifies the label ("/ 100"),
   *  the analytics page qualifies the number ("1.4s avg"). Putting a
   *  hint on the wrong side changes what it claims, so it is explicit
   *  rather than chosen here. */
  hintOn?: "label" | "value";
}) {
  const note = hint ? (
    <span
      className="ml-1 text-[10px] font-semibold"
      style={{ color: "var(--ink-faint)" }}
    >
      {hint}
    </span>
  ) : null;

  return (
    <div className="flex items-baseline justify-between gap-3 py-1.5">
      <span
        className="min-w-0 truncate text-[12px]"
        style={{ color: "var(--ink-soft)" }}
      >
        {label}
        {hintOn === "label" && note}
      </span>
      <span
        className="shrink-0 text-right text-[12px] font-bold"
        style={{ color: "var(--ink)" }}
      >
        {value}
        {hintOn === "value" && note}
      </span>
    </div>
  );
}
