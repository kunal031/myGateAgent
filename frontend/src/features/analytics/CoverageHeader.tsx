"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, CalendarClock, Compass } from "lucide-react";

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

  const card = {
    background: "var(--surface)",
    border: "var(--line-width) solid var(--line)",
  };

  return (
    /* One third coverage, two thirds what to do about it. They answer
       different questions -- where you stand, and what to open next --
       so sharing one card made the second easy to miss. */
    <section className="grid gap-3 lg:grid-cols-3">
      <div className="space-y-3 rounded-[var(--radius-lg)] p-4" style={card}>
        <div>
          <h2 className="text-[13px] font-bold" style={{ color: "var(--ink)" }}>
            Syllabus covered
          </h2>
          <p className="text-[11px]" style={{ color: "var(--ink-faint)" }}>
            {c.subjects_touched} of {c.subjects_total} subjects started
          </p>
        </div>

        <div className="space-y-2.5">
          <Bar label="Questions" done={c.questions_seen}
               total={c.questions_total} pct={c.questions_pct} />
          <Bar label="Concepts" done={c.concepts_started}
               total={c.concepts_total} pct={c.concepts_pct} />
          <Bar label="Marks" done={c.marks_touched}
               total={c.marks_total} pct={c.marks_pct} unit="marks" />
        </div>
      </div>

      <div className="space-y-3 lg:col-span-2">

      {/* The only forward-looking number on the page. Everything else is
          cumulative, which answers "how am I doing" but never "am I ahead
          or behind" -- the question a fixed exam date makes decisive. */}
      {data.pace.configured && data.pace.days_left !== undefined && (
        <div className="rounded-[var(--radius-lg)] p-4"
             style={{
               background: "var(--surface)",
               border: `var(--line-width) solid ${
                 data.pace.on_track === false
                   ? "var(--bad, #f43f5e)" : "var(--line)"
               }`,
             }}>
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <span className="flex items-center gap-1.5 text-[12px] font-bold"
                  style={{ color: "var(--ink)" }}>
              <CalendarClock className="h-3.5 w-3.5" />
              {data.pace.days_left} days to the exam
            </span>
            <span className="font-mono text-[11px]"
                  style={{ color: "var(--ink-faint)" }}>
              {data.pace.exam_date}
            </span>
          </div>

          {data.pace.on_track === null ? (
            <p className="mt-1 text-[11px]" style={{ color: "var(--ink-soft)" }}>
              Not enough study history yet to judge your pace. It needs
              four separate days with progress recorded.
            </p>
          ) : (
            <>
              <p className="mt-1 text-[11px] leading-relaxed"
                 style={{ color: "var(--ink-soft)" }}>
                <strong style={{
                  color: data.pace.on_track
                    ? "var(--ok, #10b981)" : "var(--bad, #f43f5e)",
                }}>
                  {data.pace.on_track ? "On track" : "Behind"}
                </strong>
                {" — "}
                {data.pace.current_rate} concepts a week, and{" "}
                {data.pace.needed_rate} a week would finish the{" "}
                {data.pace.concepts_remaining} left.
              </p>
              {data.pace.projected_by_exam !== null
                && data.pace.projected_by_exam !== undefined && (
                <p className="mt-0.5 font-mono text-[10px]"
                   style={{ color: "var(--ink-faint)" }}>
                  At this rate: {data.pace.projected_by_exam} of{" "}
                  {data.pace.concepts_total} concepts by exam day.
                </p>
              )}
            </>
          )}
        </div>
      )}

      {data.next_action && (
        <Link
          href={data.next_action.href}
          className="flex items-start gap-2.5 rounded-[var(--radius-lg)] p-4 hover:opacity-80"
          style={card}
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
      </div>
    </section>
  );
}
