"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, Compass } from "lucide-react";

import { CoverageSummary, fetchCoverage } from "@/lib/api";

/**
 * How much of the syllabus has been touched, and what to open next.
 *
 * This sits above everything because accuracy was the wrong headline.
 * 60% on 12 of 1,953 questions says almost nothing; "8 of 11 subjects
 * untouched" says what to do tomorrow. With fourteen months to go,
 * coverage is the number that decides the result -- accuracy only
 * becomes meaningful once there is enough of it to measure.
 *
 * One next action rather than a ranked list, because a list of
 * priorities is not a priority.
 */
function Bar({ label, done, total, pct, unit }: {
  label: string; done: number; total: number; pct: number; unit?: string;
}) {
  return (
    <div className="min-w-0 flex-1">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-[10px] font-extrabold uppercase tracking-wider"
              style={{ color: "var(--ink-faint)" }}>
          {label}
        </span>
        <span className="font-mono text-[11px] font-bold"
              style={{ color: "var(--ink)" }}>
          {pct}%
        </span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full"
           style={{ background: "var(--surface-sunk)" }}>
        {/* A floor of 2%, or a real 0.9% renders as nothing and reads as
            untouched when it is not. */}
        <div className="h-full" style={{
          width: pct > 0 ? `${Math.max(2, Math.min(pct, 100))}%` : "0%",
          background: "var(--accent)",
        }} />
      </div>
      <p className="mt-0.5 font-mono text-[10px]" style={{ color: "var(--ink-faint)" }}>
        {done.toLocaleString()} / {total.toLocaleString()}{unit ? ` ${unit}` : ""}
      </p>
    </div>
  );
}

export default function CoverageHeader() {
  const [data, setData] = useState<CoverageSummary | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchCoverage()
      .then((d) => !cancelled && setData(d))
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  if (!data) return null;
  const c = data.coverage;

  return (
    <section className="space-y-3 rounded-[var(--radius-lg)] p-4"
             style={{ background: "var(--surface)",
                      border: "var(--line-width) solid var(--line)" }}>
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="text-[13px] font-bold" style={{ color: "var(--ink)" }}>
          Syllabus covered
        </h2>
        <p className="text-[11px]" style={{ color: "var(--ink-faint)" }}>
          {c.subjects_touched} of {c.subjects_total} subjects started
        </p>
      </div>

      <div className="flex flex-wrap gap-4 sm:flex-nowrap">
        <Bar label="Questions" done={c.questions_seen}
             total={c.questions_total} pct={c.questions_pct} />
        <Bar label="Concepts" done={c.concepts_started}
             total={c.concepts_total} pct={c.concepts_pct} />
        <Bar label="Marks" done={c.marks_touched}
             total={c.marks_total} pct={c.marks_pct} unit="marks" />
      </div>

      {data.next_action && (
        <Link
          href={data.next_action.href}
          className="flex items-start gap-2.5 rounded-[var(--radius)] px-3 py-2.5 hover:opacity-80"
          style={{ background: "var(--surface-sunk)",
                   border: "var(--line-width) solid var(--line)" }}
        >
          <Compass className="mt-0.5 h-4 w-4 shrink-0"
                   style={{ color: "var(--ink)" }} />
          <span className="min-w-0 flex-1">
            <span className="block text-[13px] font-bold"
                  style={{ color: "var(--ink)" }}>
              {data.next_action.title}
            </span>
            <span className="block text-[11px] leading-relaxed"
                  style={{ color: "var(--ink-soft)" }}>
              {data.next_action.detail}
            </span>
            <span className="mt-0.5 block text-[11px] font-semibold"
                  style={{ color: "var(--ink-faint)" }}>
              {data.next_action.action}
            </span>
          </span>
          <ArrowRight className="mt-0.5 h-3.5 w-3.5 shrink-0"
                      style={{ color: "var(--ink-faint)" }} />
        </Link>
      )}
    </section>
  );
}
