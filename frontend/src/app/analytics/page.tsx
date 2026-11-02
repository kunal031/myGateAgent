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
    /* space-y-5 and no max-width, matching quiz and test: max-w-5xl
       centred this inside a shell that already pads, leaving a band of
       empty space beside the sidebar that no other page has. */
    <div className="space-y-5">
      <header className="flex items-center gap-2.5">
        <span className="flex h-8 w-8 items-center justify-center rounded-[var(--radius)]"
              style={{ background: "var(--accent)", color: "var(--ink)",
                       border: "var(--line-width) solid var(--line)" }}>
          <BarChart3 className="h-4 w-4" />
        </span>
        <h1 className="text-lg font-extrabold sm:text-xl" style={{ color: "var(--ink)" }}>
          Analytics
        </h1>
      </header>

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
