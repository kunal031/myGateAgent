"use client";

import React, { useEffect, useState } from "react";
import { ArrowRight, CheckCircle2, Clock } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

interface Progress {
  concepts_total: number;
  concepts_learned: number;
  concepts_ready: number;
  cards_due: number;
  next_concept: { id: number; name: string } | null;
  statuses: Record<string, number>;
}

interface Props {
  subjectSlug?: string;
  /** Bumped by the feed when a card is recalled, to re-read the counts. */
  refreshKey?: number;
}

/**
 * Where the student is, above the feed.
 *
 * A ranked list says nothing about position, so finishing a concept felt
 * like no progress at all. This is the smallest thing that answers "how far
 * am I, and what is next".
 */
export default function FeedHeader({ subjectSlug, refreshKey = 0 }: Props) {
  const [progress, setProgress] = useState<Progress | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const search = subjectSlug && subjectSlug !== "all"
      ? `?subject_slug=${encodeURIComponent(subjectSlug)}`
      : "";
    fetch(`${API_BASE}/api/feed/progress${search}`, { signal: controller.signal })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => data && setProgress(data))
      .catch(() => {});
    return () => controller.abort();
  }, [subjectSlug, refreshKey]);

  if (!progress || progress.concepts_total === 0) return null;

  const pct = Math.round(
    (progress.concepts_learned / progress.concepts_total) * 100,
  );

  return (
    <section
      className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-[var(--radius)] px-4 py-2.5"
      style={{
        background: "var(--surface)",
        border: "var(--line-width) solid var(--line)",
      }}
    >
      <span className="flex items-center gap-1.5 text-[12px] font-bold"
            style={{ color: "var(--ink)" }}>
        <CheckCircle2 className="h-3.5 w-3.5" />
        {progress.concepts_learned} of {progress.concepts_total} concepts
      </span>

      <span
        className="h-1.5 w-28 overflow-hidden rounded-[var(--radius-pill)]"
        style={{
          background: "var(--surface-sunk)",
          border: "var(--line-width) solid var(--line)",
        }}
        aria-label={`${pct}% learned`}
      >
        <span
          className="block h-full transition-all duration-500"
          style={{ width: `${pct}%`, background: "var(--success)" }}
        />
      </span>

      {progress.cards_due > 0 && (
        <span className="flex items-center gap-1 text-[11px] font-bold"
              style={{ color: "var(--ink)" }}>
          <Clock className="h-3 w-3" />
          {progress.cards_due} due
        </span>
      )}

      <span className="text-[11px] font-semibold" style={{ color: "var(--ink-faint)" }}>
        {progress.concepts_ready} ready to study
      </span>

      {progress.next_concept && (
        <span className="ml-auto flex min-w-0 items-center gap-1 text-[11px] font-bold"
              style={{ color: "var(--ink-soft)" }}>
          <ArrowRight className="h-3 w-3 shrink-0" />
          <span className="truncate">Next: {progress.next_concept.name}</span>
        </span>
      )}
    </section>
  );
}
