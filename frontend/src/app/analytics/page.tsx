"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";

import CoverageHeader from "@/features/analytics/CoverageHeader";
import DeepPanels from "@/features/analytics/DeepPanels";
import SubjectDrilldown from "@/features/analytics/SubjectDrilldown";
import InsightsPanel from "@/features/analytics/InsightsPanel";
import { ArrowRight, BarChart3, ShieldAlert } from "lucide-react";
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

      <CoverageHeader />

      {(stats?.active_mistakes_count ?? 0) > 0 && (
        <Link
          href="/quiz?review=mistakes"
          className="flex items-center gap-2.5 rounded-[var(--radius-lg)] px-4 py-3 hover:opacity-80"
          style={{ background: "var(--surface)",
                   border: "var(--line-width) solid var(--line)" }}
        >
          <ShieldAlert className="h-4 w-4 shrink-0" style={{ color: "var(--ink)" }} />
          <span className="min-w-0 flex-1 text-[13px]" style={{ color: "var(--ink-soft)" }}>
            <strong style={{ color: "var(--ink)" }}>
              {stats?.active_mistakes_count} question
              {stats?.active_mistakes_count === 1 ? "" : "s"}
            </strong>{" "}
            answered wrong and not yet mastered.
          </span>
          <ArrowRight className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--ink-faint)" }} />
        </Link>
      )}


      <SubjectDrilldown />

      <DeepPanels />

      <InsightsPanel />
    </div>
  );
}
