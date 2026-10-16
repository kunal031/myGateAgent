"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { CheckCircle2, ChevronDown, MinusCircle, XCircle } from "lucide-react";

import MathText from "@/components/MathText";
import {
  ExamResult as ExamResultData, ExamResultRow, SolutionResponse,
  fetchExamResult, fetchSolution,
} from "@/lib/api";
import { formatClock } from "./palette";

export default function ExamResult({ examId }: { examId: number }) {
  const [result, setResult] = useState<ExamResultData | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const [solutions, setSolutions] = useState<Record<number, SolutionResponse>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchExamResult(examId)
      .then((data) => !cancelled && setResult(data))
      .catch(() => !cancelled && setError("Could not load this result."));
    return () => { cancelled = true; };
  }, [examId]);

  const toggle = async (row: ExamResultRow) => {
    if (open === row.position) { setOpen(null); return; }
    setOpen(row.position);
    if (solutions[row.question_id]) return;
    try {
      const solution = await fetchSolution(row.question_id);
      setSolutions((prev) => ({ ...prev, [row.question_id]: solution }));
    } catch {
      // The row already shows the correct answer; a missing worked solution
      // is not worth an error banner.
    }
  };

  if (error) return <p className="py-16 text-center text-sm font-semibold"
                       style={{ color: "var(--ink)" }}>{error}</p>;
  if (!result) return <p className="py-16 text-center text-xs font-semibold"
                         style={{ color: "var(--ink-faint)" }}>Loading result...</p>;

  const stats = [
    { label: "Score", value: `${result.score} / ${result.max_score}`, tone: "var(--accent)" },
    { label: "Correct", value: result.correct_count, tone: "var(--success)" },
    { label: "Wrong", value: result.wrong_count, tone: "var(--danger)" },
    { label: "Skipped", value: result.unattempted_count, tone: "var(--surface-sunk)" },
    { label: "Accuracy", value: `${result.accuracy}%`, tone: "var(--info)" },
    { label: "Time", value: formatClock(result.elapsed_seconds), tone: "var(--warning)" },
  ];

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-extrabold" style={{ color: "var(--ink)" }}>
            {result.name}
          </h1>
          <p className="text-[11px] font-semibold" style={{ color: "var(--ink-faint)" }}>
            Submitted · {result.total_questions} questions
          </p>
        </div>
        <Link
          href="/test"
          className="flex min-h-11 items-center rounded-[var(--radius-pill)] px-4 text-xs font-bold"
          style={{ background: "var(--surface)", color: "var(--ink)",
                   border: "var(--line-width) solid var(--line)" }}
        >
          New test
        </Link>
      </header>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {stats.map((stat) => (
          <div key={stat.label} className="rounded-[var(--radius)] px-3 py-2.5"
               style={{ background: stat.tone,
                        border: "var(--line-width) solid var(--line)" }}>
            <p className="text-[10px] font-bold uppercase tracking-wider"
               style={{ color: "var(--ink-faint)" }}>{stat.label}</p>
            <p className="text-base font-extrabold" style={{ color: "var(--ink)" }}>
              {stat.value}
            </p>
          </div>
        ))}
      </div>

      <div className="space-y-2">
        {result.questions.map((row) => {
          const expanded = open === row.position;
          const solution = solutions[row.question_id];
          const Icon = row.is_correct === null ? MinusCircle
                     : row.is_correct ? CheckCircle2 : XCircle;
          const tone = row.is_correct === null ? "var(--surface-sunk)"
                     : row.is_correct ? "var(--success)" : "var(--danger)";

          return (
            <article key={row.position} className="overflow-hidden rounded-[var(--radius)]"
                     style={{ background: "var(--surface)",
                              border: "var(--line-width) solid var(--line)" }}>
              <button
                type="button"
                onClick={() => toggle(row)}
                aria-expanded={expanded}
                className="flex w-full items-center gap-3 px-3 py-3 text-left"
              >
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[var(--radius)] text-xs font-extrabold"
                      style={{ background: tone,
                               border: "var(--line-width) solid var(--line)",
                               color: "var(--ink)" }}>
                  {row.position}
                </span>
                <Icon className="h-4 w-4 shrink-0" style={{ color: "var(--ink)" }} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-xs font-semibold"
                        style={{ color: "var(--ink)" }}>
                    {row.content.slice(0, 90)}
                  </span>
                  <span className="text-[10px] font-semibold" style={{ color: "var(--ink-faint)" }}>
                    {row.subject_name} · you: {row.user_answer || "—"} · correct: {row.correct_answer}
                    {" · "}{row.marks_obtained > 0 ? "+" : ""}{row.marks_obtained}
                  </span>
                </span>
                <ChevronDown className="h-4 w-4 shrink-0 transition-transform"
                             style={{ color: "var(--ink-faint)",
                                      transform: expanded ? "rotate(180deg)" : "none" }} />
              </button>

              {expanded && (
                <div className="space-y-3 border-t px-3 py-3"
                     style={{ borderColor: "var(--line)" }}>
                  <div className="overflow-x-auto text-[13px]" style={{ color: "var(--ink-soft)" }}>
                    <MathText text={row.content} />
                  </div>
                  <div className="rounded-[var(--radius)] px-3 py-2.5"
                       style={{ background: "var(--surface-muted)",
                                border: "var(--line-width) solid var(--line)" }}>
                    <p className="mb-1 text-[10px] font-extrabold uppercase tracking-wider"
                       style={{ color: "var(--ink-faint)" }}>
                      Solution
                    </p>
                    <div className="overflow-x-auto text-[13px]" style={{ color: "var(--ink)" }}>
                      {solution
                        ? <MathText text={solution.solution} />
                        : <span style={{ color: "var(--ink-faint)" }}>Loading…</span>}
                    </div>
                    {solution?.provenance && (
                      <p className="mt-2 text-[10px] font-semibold" style={{ color: "var(--ink-faint)" }}>
                        {solution.provenance}
                      </p>
                    )}
                  </div>
                </div>
              )}
            </article>
          );
        })}
      </div>
    </div>
  );
}
