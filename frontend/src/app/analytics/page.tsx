"use client";

import React, { useEffect, useState } from "react";

import DeepPanels from "@/features/analytics/DeepPanels";
import SubjectDrilldown from "@/features/analytics/SubjectDrilldown";
import InsightsPanel from "@/features/analytics/InsightsPanel";
import {
  BarChart3, BookOpen, CheckCircle, ShieldAlert, TrendingUp,
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

      <DeepPanels />

      {/* KPI Cards Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {/* Total Questions Attempted */}
        <div className="p-4 rounded-xl bg-[var(--surface)] border border-[var(--line)]">
          <div className="flex items-center justify-between text-[var(--ink-faint)] text-xs font-semibold">
            <span>Attempted</span>
            <BookOpen className="w-3.5 h-3.5 text-[var(--ink)]" />
          </div>
          <div className="text-2xl font-black text-[var(--ink)] font-mono mt-1">
            {stats?.total_attempts || 0}
          </div>
          <div className="text-[10px] text-[var(--ink-faint)] font-mono mt-0.5">
            {stats?.correct_attempts || 0} correct
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
            <span>Marks</span>
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

      <SubjectDrilldown />

      <InsightsPanel />
    </div>
  );
}
