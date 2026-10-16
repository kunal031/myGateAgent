"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { 
  BarChart3, 
  CheckCircle, 
  Flame, 
  TrendingUp, 
  BookOpen, 
  ArrowRight,
  ShieldAlert
} from "lucide-react";
import { fetchStats, StatsSummary } from "@/lib/api";

export default function AnalyticsPage() {
  const [stats, setStats] = useState<StatsSummary | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    async function load() {
      try {
        const data = await fetchStats();
        setStats(data);
      } catch (err) {
        console.error("Failed to load statistics", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto py-20 text-center text-[var(--ink-faint)] text-xs font-mono">
        Loading analytics...
      </div>
    );
  }

  const accuracy = stats?.accuracy || 0;

  return (
    <div className="max-w-5xl mx-auto space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between pb-2 border-b border-[var(--line)]">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-[var(--accent)] border border-[var(--line)] flex items-center justify-center text-[var(--ink)]">
            <BarChart3 className="w-4 h-4" />
          </div>
          <div>
            <h1 className="text-xl font-black tracking-tight text-[var(--ink)] flex items-center gap-2">
              Performance Analytics
            </h1>
          </div>
        </div>
      </div>

      {/* KPI Cards Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {/* Total Questions Attempted */}
        <div className="p-4 rounded-xl bg-[var(--surface)] border border-[var(--line)]">
          <div className="flex items-center justify-between text-[var(--ink-faint)] text-xs font-semibold">
            <span>Drilled</span>
            <BookOpen className="w-3.5 h-3.5 text-[var(--ink)]" />
          </div>
          <div className="text-2xl font-black text-[var(--ink)] font-mono mt-1">
            {stats?.total_attempts || 0}
          </div>
          <div className="text-[10px] text-[var(--ink-faint)] font-mono mt-0.5">
            {stats?.correct_attempts || 0} solved
          </div>
        </div>

        {/* Global Accuracy */}
        <div className="p-4 rounded-xl bg-[var(--surface)] border border-[var(--line)]">
          <div className="flex items-center justify-between text-[var(--ink-faint)] text-xs font-semibold">
            <span>Accuracy</span>
            <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />
          </div>
          <div className="text-2xl font-black text-emerald-400 font-mono mt-1">
            {accuracy}%
          </div>
          <div className="text-[10px] text-[var(--ink-faint)] font-mono mt-0.5">
            Target &gt; 85%
          </div>
        </div>

        {/* Total Score Accrued */}
        <div className="p-4 rounded-xl bg-[var(--surface)] border border-[var(--line)]">
          <div className="flex items-center justify-between text-[var(--ink-faint)] text-xs font-semibold">
            <span>Net Marks</span>
            <CheckCircle className="w-3.5 h-3.5 text-violet-400" />
          </div>
          <div className="text-2xl font-black text-violet-300 font-mono mt-1">
            {stats?.total_marks_earned || 0}
          </div>
          <div className="text-[10px] text-[var(--ink-faint)] font-mono mt-0.5">
            Net score
          </div>
        </div>

        {/* Active Mistakes in Registry */}
        <div className="p-4 rounded-xl bg-[var(--surface)] border border-[var(--line)]">
          <div className="flex items-center justify-between text-[var(--ink-faint)] text-xs font-semibold">
            <span>Active Mistakes</span>
            <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
          </div>
          <div className="text-2xl font-black text-amber-400 font-mono mt-1">
            {stats?.active_mistakes_count || 0}
          </div>
          <div className="text-[10px] text-[var(--ink-faint)] font-mono mt-0.5">
            Pending mastery
          </div>
        </div>
      </div>

      {/* Subject-Wise Mastery Table */}
      <div className="rounded-xl bg-[var(--surface)] border border-[var(--line)] overflow-hidden shadow-lg">
        <div className="p-3.5 border-b border-[var(--line)] flex items-center justify-between">
          <h3 className="font-bold text-sm text-[var(--ink)] flex items-center gap-2">
            Subject Breakdown
            <span className="text-[10px] font-mono text-[var(--ink-faint)] font-normal">
              (11 Core Subjects)
            </span>
          </h3>
          <Link
            href="/quiz"
            className="text-xs font-bold text-[var(--ink)] hover:text-[var(--ink)] flex items-center gap-1"
          >
            Practice
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-[var(--ink-soft)]">
            <thead className="bg-[var(--surface-sunk)] text-[var(--ink-faint)] font-mono uppercase text-[10px] border-b border-[var(--line)]">
              <tr>
                <th className="py-2.5 px-3.5">Subject</th>
                <th className="py-2.5 px-3.5">Weight</th>
                <th className="py-2.5 px-3.5">Attempts</th>
                <th className="py-2.5 px-3.5">Accuracy</th>
                <th className="py-2.5 px-3.5">Score</th>
                <th className="py-2.5 px-3.5">Mistakes</th>
                <th className="py-2.5 px-3.5 text-right">Drill</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--line)] font-medium">
              {stats?.subject_stats.map((s) => (
                <tr key={s.subject_id} className="hover:bg-[var(--surface-sunk)] transition">
                  <td className="py-2.5 px-3.5 text-[var(--ink)] font-semibold">
                    {s.subject_name}
                  </td>
                  <td className="py-2.5 px-3.5 font-mono text-[var(--ink-faint)]">
                    ~{s.weightage_marks}M
                  </td>
                  <td className="py-2.5 px-3.5 font-mono text-[var(--ink-soft)]">
                    {s.attempts}
                  </td>
                  <td className="py-2.5 px-3.5">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold">
                        {s.attempts > 0 ? `${s.accuracy}%` : "-"}
                      </span>
                      {s.attempts > 0 && (
                        <div className="w-14 bg-[var(--surface-sunk)] h-1 rounded-full overflow-hidden">
                          <div
                            className={`h-full ${
                              s.accuracy >= 75
                                ? "bg-emerald-400"
                                : s.accuracy >= 50
                                ? "bg-amber-400"
                                : "bg-rose-500"
                            }`}
                            style={{ width: `${s.accuracy}%` }}
                          ></div>
                        </div>
                      )}
                    </div>
                  </td>
                  <td className="py-2.5 px-3.5 font-mono font-bold text-violet-300">
                    {s.marks_earned}
                  </td>
                  <td className="py-2.5 px-3.5">
                    {s.unresolved_mistakes > 0 ? (
                      <span className="inline-flex items-center gap-1 px-1.5 py-0.2 rounded bg-amber-500/15 text-amber-300 font-bold text-[10px] border border-amber-500/30">
                        <Flame className="w-3 h-3 text-amber-400" />
                        {s.unresolved_mistakes}
                      </span>
                    ) : (
                      <span className="text-[var(--ink-faint)] text-[10px] font-mono">0</span>
                    )}
                  </td>
                  <td className="py-2.5 px-3.5 text-right">
                    <Link
                      href={`/quiz?subject=${s.subject_slug}`}
                      className="px-2 py-0.5 rounded bg-[var(--surface-sunk)] hover:bg-[var(--accent)] text-[var(--ink)] text-[11px] font-bold transition"
                    >
                      Start
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
