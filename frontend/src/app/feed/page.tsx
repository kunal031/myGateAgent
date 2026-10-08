"use client";

import React, { useEffect, useState } from "react";
import { Flame, Loader2, RefreshCw } from "lucide-react";

import FeedCard from "@/features/feed/FeedCard";
import {
  useInfiniteFeed,
  useScrollSentinel,
} from "@/features/feed/useInfiniteFeed";
import { SubjectItem, fetchSyllabus } from "@/lib/api";

const CARD_TYPES = [
  { value: "all", label: "All types" },
  { value: "TRAP", label: "Trap alerts" },
  { value: "FORMULA", label: "Formulas" },
  { value: "CONCEPT", label: "Core concepts" },
  { value: "SHORTCUT", label: "Shortcuts" },
];

export default function FeedPage() {
  const [subjects, setSubjects] = useState<SubjectItem[]>([]);
  const [subjectSlug, setSubjectSlug] = useState("all");
  const [cardType, setCardType] = useState("all");
  const [mastered, setMastered] = useState<Set<number>>(new Set());

  const { cards, loading, loadingMore, error, total, hasMore, loadMore, refresh } =
    useInfiniteFeed(subjectSlug, cardType);

  const sentinelRef = useScrollSentinel(loadMore, hasMore && !loading);

  useEffect(() => {
    let cancelled = false;
    fetchSyllabus()
      .then((data) => {
        if (!cancelled) setSubjects(data);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const toggleMastered = (id: number) =>
    setMastered((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const selectStyle = {
    background: "var(--surface)",
    border: "var(--line-width) solid var(--line)",
    color: "var(--ink)",
  };

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span
            className="flex h-9 w-9 items-center justify-center rounded-[var(--radius)]"
            style={{
              background: "var(--accent)",
              border: "var(--line-width) solid var(--line)",
              boxShadow: "var(--shadow-sm)",
            }}
          >
            <Flame className="h-4 w-4" style={{ color: "var(--ink)" }} />
          </span>
          <div>
            <h1 className="text-lg font-extrabold leading-tight sm:text-xl" style={{ color: "var(--ink)" }}>
              Concept &amp; Trap Feed
            </h1>
            <p className="text-[11px] font-semibold" style={{ color: "var(--ink-faint)" }}>
              {cards.length} of {total} cards
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={refresh}
          className="flex min-h-11 items-center gap-1.5 rounded-[var(--radius-pill)] px-3.5 text-xs font-bold"
          style={{
            background: "var(--surface)",
            border: "var(--line-width) solid var(--line)",
            color: "var(--ink)",
            boxShadow: "var(--shadow-sm)",
          }}
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </button>
      </header>

      <div className="flex flex-wrap gap-2">
        <select
          value={subjectSlug}
          onChange={(e) => setSubjectSlug(e.target.value)}
          aria-label="Filter by subject"
          className="min-h-11 flex-1 rounded-[var(--radius-pill)] px-3.5 text-xs font-semibold sm:flex-none"
          style={selectStyle}
        >
          <option value="all">All subjects</option>
          {subjects.map((s) => (
            <option key={s.slug} value={s.slug}>
              {s.name}
            </option>
          ))}
        </select>

        <select
          value={cardType}
          onChange={(e) => setCardType(e.target.value)}
          aria-label="Filter by card type"
          className="min-h-11 flex-1 rounded-[var(--radius-pill)] px-3.5 text-xs font-semibold sm:flex-none"
          style={selectStyle}
        >
          {CARD_TYPES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
      </div>

      {error && (
        <p
          className="rounded-[var(--radius)] px-4 py-3 text-xs font-semibold"
          style={{
            background: "var(--danger)",
            border: "var(--line-width) solid var(--line)",
            color: "var(--ink)",
          }}
        >
          {error}
        </p>
      )}

      {loading ? (
        <p className="py-16 text-center text-xs font-semibold" style={{ color: "var(--ink-faint)" }}>
          Loading cards...
        </p>
      ) : cards.length === 0 ? (
        <p
          className="rounded-[var(--radius-lg)] py-14 text-center text-xs font-semibold"
          style={{
            background: "var(--surface)",
            border: "var(--line-width) solid var(--line)",
            color: "var(--ink-faint)",
          }}
        >
          No cards match this filter.
        </p>
      ) : (
        <div className="space-y-4">
          {cards.map((card) => (
            <FeedCard
              key={card.id}
              card={card}
              mastered={mastered.has(card.id)}
              onToggleMastered={toggleMastered}
            />
          ))}
        </div>
      )}

      {/* Sentinel: loading starts 600px before this scrolls into view. */}
      {hasMore && !loading && <div ref={sentinelRef} aria-hidden className="h-px" />}

      {loadingMore && (
        <p className="flex items-center justify-center gap-2 py-6 text-xs font-semibold" style={{ color: "var(--ink-faint)" }}>
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading more...
        </p>
      )}

      {!hasMore && cards.length > 0 && (
        <p className="py-6 text-center text-xs font-semibold" style={{ color: "var(--ink-faint)" }}>
          You have reached the end.
        </p>
      )}
    </div>
  );
}
