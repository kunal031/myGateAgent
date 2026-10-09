"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Award, History, Layers, Play, Settings2 } from "lucide-react";

import {
  ExamPatterns, ExamSummary, fetchExamHistory, fetchExamPatterns, startExam,
} from "@/lib/api";
import { formatClock } from "@/features/exam/palette";

type Mode = "full" | "subject" | "custom";

const MODES: { key: Mode; title: string; blurb: string; icon: typeof Award }[] = [
  { key: "full", title: "Full mock", blurb: "Whole syllabus, exam pattern", icon: Award },
  { key: "subject", title: "Subject test", blurb: "One subject in depth", icon: Layers },
  { key: "custom", title: "Custom mix", blurb: "Pick subjects and length", icon: Settings2 },
];

const COUNTS = [10, 20, 30, 50];
const DURATIONS = [15, 30, 45, 60, 90, 180];

export default function TestPage() {
  const router = useRouter();
  const [patterns, setPatterns] = useState<ExamPatterns | null>(null);
  const [history, setHistory] = useState<ExamSummary[]>([]);
  const [mode, setMode] = useState<Mode>("full");
  const [subject, setSubject] = useState("");
  const [picked, setPicked] = useState<string[]>([]);
  const [count, setCount] = useState(20);
  const [minutes, setMinutes] = useState(45);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchExamPatterns()
      .then((data) => {
        if (cancelled) return;
        setPatterns(data);
        const first = data.subjects.find((s) => s.question_count > 0);
        if (first) setSubject(first.slug);
      })
      .catch(() => !cancelled && setError("Could not load test patterns."));
    fetchExamHistory(10).then((h) => !cancelled && setHistory(h)).catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const fullPreset = patterns?.presets.find((p) => p.key === "full");

  // Only offer subjects that actually have questions.
  const available = useMemo(
    () => (patterns?.subjects ?? []).filter((s) => s.question_count > 0),
    [patterns],
  );

  const launch = async () => {
    setStarting(true);
    setError(null);
    try {
      const session = await startExam({
        pattern: mode,
        subject_slug: mode === "subject" ? subject : undefined,
        subject_slugs: mode === "custom"
          ? (picked.length ? picked : available.map((s) => s.slug))
          : undefined,
        questions: count,
        duration_minutes: mode === "full" ? 180 : minutes,
      });
      router.push(`/test/${session.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start the test.");
      setStarting(false);
    }
  };

  const chip = (active: boolean) => ({
    background: active ? "var(--accent)" : "var(--surface)",
    border: "var(--line-width) solid var(--line)",
    color: "var(--ink)",
    boxShadow: active ? "var(--shadow-sm)" : "none",
  });

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-lg font-extrabold sm:text-xl" style={{ color: "var(--ink)" }}>
          Mock Test
        </h1>
        <p className="text-[11px] font-semibold" style={{ color: "var(--ink-faint)" }}>
          Full-length, subject or topic tests under exam conditions.
          {patterns && ` ${patterns.total_questions_available} questions available.`}
        </p>
      </header>

      {error && (
        <p className="rounded-[var(--radius)] px-4 py-3 text-xs font-semibold"
           style={{ background: "var(--danger)", color: "var(--ink)",
                    border: "var(--line-width) solid var(--line)" }}>
          {error}
        </p>
      )}

      <section className="grid gap-3 sm:grid-cols-3">
        {MODES.map((option) => {
          const Icon = option.icon;
          const active = mode === option.key;
          return (
            <button
              key={option.key}
              type="button"
              onClick={() => setMode(option.key)}
              className="rounded-[var(--radius-lg)] p-4 text-left"
              style={{
                background: active ? "var(--accent)" : "var(--surface)",
                border: `${active ? "3px" : "var(--line-width)"} solid var(--line)`,
                boxShadow: active ? "var(--shadow)" : "var(--shadow-sm)",
              }}
            >
              <Icon className="mb-2 h-5 w-5" style={{ color: "var(--ink)" }} />
              <h2 className="text-sm font-extrabold" style={{ color: "var(--ink)" }}>
                {option.title}
              </h2>
              <p className="text-[11px] font-semibold" style={{ color: "var(--ink-faint)" }}>
                {option.blurb}
              </p>
            </button>
          );
        })}
      </section>

      <section className="space-y-4 rounded-[var(--radius-lg)] p-4"
               style={{ background: "var(--surface)",
                        border: "var(--line-width) solid var(--line)",
                        boxShadow: "var(--shadow-sm)" }}>
        {mode === "full" && fullPreset && (
          <p className="text-xs font-semibold" style={{ color: "var(--ink-soft)" }}>
            {fullPreset.total_questions} questions · {fullPreset.total_marks} marks ·{" "}
            {fullPreset.duration_minutes} minutes, following the real GATE pattern.
          </p>
        )}

        {mode === "subject" && (
          <div className="space-y-2">
            <p className="text-[10px] font-extrabold uppercase tracking-wider"
               style={{ color: "var(--ink-faint)" }}>Subject</p>
            <div className="flex flex-wrap gap-2">
              {available.map((s) => (
                <button key={s.slug} type="button" onClick={() => setSubject(s.slug)}
                        className="min-h-10 rounded-[var(--radius-pill)] px-3 text-[11px] font-bold"
                        style={chip(subject === s.slug)}>
                  {s.name} <span style={{ color: "var(--ink-faint)" }}>({s.question_count})</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {mode === "custom" && (
          <div className="space-y-2">
            <p className="text-[10px] font-extrabold uppercase tracking-wider"
               style={{ color: "var(--ink-faint)" }}>
              Subjects {picked.length === 0 && "(none selected = all)"}
            </p>
            <div className="flex flex-wrap gap-2">
              {available.map((s) => (
                <button key={s.slug} type="button"
                        onClick={() => setPicked((prev) =>
                          prev.includes(s.slug)
                            ? prev.filter((p) => p !== s.slug)
                            : [...prev, s.slug])}
                        className="min-h-10 rounded-[var(--radius-pill)] px-3 text-[11px] font-bold"
                        style={chip(picked.includes(s.slug))}>
                  {s.name}
                </button>
              ))}
            </div>
          </div>
        )}

        {mode !== "full" && (
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-2">
              <p className="text-[10px] font-extrabold uppercase tracking-wider"
                 style={{ color: "var(--ink-faint)" }}>Questions</p>
              <div className="flex flex-wrap gap-2">
                {COUNTS.map((n) => (
                  <button key={n} type="button" onClick={() => setCount(n)}
                          className="min-h-10 rounded-[var(--radius-pill)] px-3.5 text-[11px] font-bold"
                          style={chip(count === n)}>{n}</button>
                ))}
              </div>
            </div>
            <div className="space-y-2">
              <p className="text-[10px] font-extrabold uppercase tracking-wider"
                 style={{ color: "var(--ink-faint)" }}>Minutes</p>
              <div className="flex flex-wrap gap-2">
                {DURATIONS.map((n) => (
                  <button key={n} type="button" onClick={() => setMinutes(n)}
                          className="min-h-10 rounded-[var(--radius-pill)] px-3.5 text-[11px] font-bold"
                          style={chip(minutes === n)}>{n}</button>
                ))}
              </div>
            </div>
          </div>
        )}

        <button
          type="button"
          onClick={launch}
          disabled={starting || !patterns}
          className="flex min-h-12 w-full items-center justify-center gap-2 rounded-[var(--radius-pill)] text-sm font-extrabold disabled:opacity-50 sm:w-auto sm:px-8"
          style={{ background: "var(--accent)", color: "var(--ink)",
                   border: "var(--line-width) solid var(--line)",
                   boxShadow: "var(--shadow)" }}
        >
          <Play className="h-4 w-4" />
          {starting ? "Preparing paper..." : "Start test"}
        </button>
      </section>

      <section className="space-y-2">
        <h2 className="flex items-center gap-2 text-sm font-extrabold"
            style={{ color: "var(--ink)" }}>
          <History className="h-4 w-4" />
          Performance history
        </h2>

        {history.length === 0 ? (
          <p className="rounded-[var(--radius)] px-4 py-6 text-center text-xs font-semibold"
             style={{ background: "var(--surface)", color: "var(--ink-faint)",
                      border: "var(--line-width) solid var(--line)" }}>
            No tests yet. Your scores will appear here.
          </p>
        ) : (
          <ul className="space-y-2">
            {history.map((h) => (
              <li key={h.id}>
                <Link
                  href={h.status === "submitted" ? `/test/${h.id}/result` : `/test/${h.id}`}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-[var(--radius)] px-3 py-2.5"
                  style={{ background: "var(--surface)",
                           border: "var(--line-width) solid var(--line)" }}
                >
                  <span className="min-w-0">
                    <span className="block truncate text-xs font-bold" style={{ color: "var(--ink)" }}>
                      {h.name}
                    </span>
                    <span className="text-[10px] font-semibold" style={{ color: "var(--ink-faint)" }}>
                      {h.started_at?.slice(0, 16).replace("T", " ")} ·{" "}
                      {h.status === "submitted"
                        ? `${h.correct_count}✓ ${h.wrong_count}✗ ${h.unattempted_count}– · ${formatClock(h.elapsed_seconds)}`
                        : "in progress"}
                    </span>
                  </span>
                  <span className="rounded-[var(--radius-pill)] px-3 py-1 text-xs font-extrabold"
                        style={{ background: h.status === "submitted" ? "var(--success)" : "var(--warning)",
                                 border: "var(--line-width) solid var(--line)",
                                 color: "var(--ink)" }}>
                    {h.status === "submitted" ? `${h.score}/${h.max_score}` : "Resume"}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
