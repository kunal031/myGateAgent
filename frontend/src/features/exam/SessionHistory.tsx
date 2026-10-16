"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { History } from "lucide-react";

import { ExamSummary, fetchExamHistory } from "@/lib/api";
import { formatClock } from "./palette";

type Range = "all" | "7d" | "30d";

const RANGES: { key: Range; label: string }[] = [
  { key: "all", label: "All time" },
  { key: "7d", label: "Last 7 days" },
  { key: "30d", label: "Last 30 days" },
];

function sinceFor(range: Range): string | undefined {
  if (range === "all") return undefined;
  const days = range === "7d" ? 7 : 30;
  const date = new Date();
  date.setDate(date.getDate() - days);
  return date.toISOString().slice(0, 10);
}

interface Props {
  kind: "quiz" | "test";
  subjects: { slug: string; name: string }[];
  /** Where a finished session opens; a quiz and a test review differently. */
  resultHref: (id: number) => string;
  resumeHref: (id: number) => string;
}

/** Dated history with subject and date-range filters. */
export default function SessionHistory({
  kind, subjects, resultHref, resumeHref,
}: Props) {
  const [sessions, setSessions] = useState<ExamSummary[]>([]);
  const [subject, setSubject] = useState("all");
  const [range, setRange] = useState<Range>("all");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetchExamHistory({ limit: 30, kind, subjectSlug: subject, since: sinceFor(range) })
      .then((data) => !cancelled && setSessions(data))
      .catch(() => {})
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [kind, subject, range]);

  // Group by calendar day so a session is easy to find by when it happened.
  const byDay = useMemo(() => {
    const groups = new Map<string, ExamSummary[]>();
    for (const session of sessions) {
      const day = session.started_at?.slice(0, 10) ?? "unknown";
      groups.set(day, [...(groups.get(day) ?? []), session]);
    }
    return [...groups.entries()];
  }, [sessions]);

  const chip = (active: boolean) => ({
    background: active ? "var(--accent)" : "var(--surface)",
    border: "var(--line-width) solid var(--line)",
    color: "var(--ink)",
  });

  return (
    <section className="space-y-3">
      <h2 className="flex items-center gap-2 text-sm font-extrabold"
          style={{ color: "var(--ink)" }}>
        <History className="h-4 w-4" />
        History
      </h2>

      <div className="flex flex-wrap items-center gap-2">
        <select
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          aria-label="Filter history by subject"
          className="min-h-10 rounded-[var(--radius-pill)] px-3 text-[11px] font-bold"
          style={chip(subject !== "all")}
        >
          <option value="all">All subjects</option>
          {subjects.map((s) => (
            <option key={s.slug} value={s.slug}>{s.name}</option>
          ))}
        </select>

        {RANGES.map((r) => (
          <button key={r.key} type="button" onClick={() => setRange(r.key)}
                  className="min-h-10 rounded-[var(--radius-pill)] px-3 text-[11px] font-bold"
                  style={chip(range === r.key)}>
            {r.label}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="py-6 text-center text-xs font-semibold" style={{ color: "var(--ink-faint)" }}>
          Loading history...
        </p>
      ) : byDay.length === 0 ? (
        <p className="rounded-[var(--radius)] px-4 py-6 text-center text-xs font-semibold"
           style={{ background: "var(--surface)", color: "var(--ink-faint)",
                    border: "var(--line-width) solid var(--line)" }}>
          Nothing here yet for this filter.
        </p>
      ) : (
        <div className="space-y-4">
          {byDay.map(([day, items]) => (
            <div key={day} className="space-y-2">
              <p className="text-[10px] font-extrabold uppercase tracking-wider"
                 style={{ color: "var(--ink-faint)" }}>
                {new Date(day).toLocaleDateString(undefined, {
                  weekday: "short", day: "numeric", month: "short",
                })}
              </p>
              <ul className="space-y-2">
                {items.map((s) => {
                  const done = s.status === "submitted";
                  return (
                    <li key={s.id}>
                      <Link
                        href={done ? resultHref(s.id) : resumeHref(s.id)}
                        className="flex flex-wrap items-center justify-between gap-2 rounded-[var(--radius)] px-3 py-2.5"
                        style={{ background: "var(--surface)",
                                 border: "var(--line-width) solid var(--line)" }}
                      >
                        <span className="min-w-0">
                          <span className="block truncate text-xs font-bold"
                                style={{ color: "var(--ink)" }}>
                            {s.name}
                          </span>
                          <span className="text-[10px] font-semibold"
                                style={{ color: "var(--ink-faint)" }}>
                            {done
                              ? `${s.correct_count}✓ ${s.wrong_count}✗ ${s.unattempted_count}– · ${s.accuracy}% · ${formatClock(s.elapsed_seconds)}`
                              : "in progress"}
                          </span>
                        </span>
                        <span className="rounded-[var(--radius-pill)] px-3 py-1 text-xs font-extrabold"
                              style={{ background: done ? "var(--success)" : "var(--warning)",
                                       border: "var(--line-width) solid var(--line)",
                                       color: "var(--ink)" }}>
                          {done ? `${s.score}/${s.max_score}` : "Resume"}
                        </span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
