"use client";

import React, { useEffect, useState } from "react";
import { AlertTriangle, Info, Lightbulb } from "lucide-react";

import { Insight, fetchInsights } from "@/lib/api";

const TONE: Record<string, { background: string; icon: typeof Info }> = {
  high: { background: "var(--danger)", icon: AlertTriangle },
  medium: { background: "var(--warning)", icon: Info },
  low: { background: "var(--surface-muted)", icon: Lightbulb },
};

/**
 * What to do differently, above the numbers that justify it.
 *
 * Analytics that only describe are easy to read and ignore. Each entry
 * states a finding, the evidence behind it, and one next step -- and the
 * backend only emits one when it has enough attempts to mean it.
 */
export default function InsightsPanel() {
  const [insights, setInsights] = useState<Insight[] | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetchInsights()
      .then((rows) => !controller.signal.aborted && setInsights(rows))
      .catch(() => setInsights([]));
    return () => controller.abort();
  }, []);

  if (insights === null || insights.length === 0) return null;

  return (
    <section className="space-y-2">
      <h2 className="text-[11px] font-extrabold uppercase tracking-wider"
          style={{ color: "var(--ink-faint)" }}>
        What to fix next
      </h2>

      {insights.map((insight, i) => {
        const tone = TONE[insight.severity] ?? TONE.low;
        const Icon = tone.icon;
        return (
          <article
            key={`${insight.kind}-${i}`}
            className="flex gap-2.5 rounded-[var(--radius)] px-3 py-2.5"
            style={{
              background: "var(--surface)",
              border: "var(--line-width) solid var(--line)",
            }}
          >
            <span
              className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-[var(--radius-pill)]"
              style={{
                background: tone.background,
                border: "var(--line-width) solid var(--line)",
              }}
            >
              <Icon className="h-3 w-3" style={{ color: "var(--ink)" }} />
            </span>
            <div className="min-w-0">
              <p className="text-[13px] font-bold" style={{ color: "var(--ink)" }}>
                {insight.title}
              </p>
              <p className="mt-0.5 text-[12px] leading-relaxed"
                 style={{ color: "var(--ink-soft)" }}>
                {insight.detail}
              </p>
              <p className="mt-1 text-[11px] font-semibold"
                 style={{ color: "var(--ink-faint)" }}>
                → {insight.action}
              </p>
            </div>
          </article>
        );
      })}
    </section>
  );
}
