"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

import FeedCard from "@/features/feed/FeedCard";
import { useHideOnScroll } from "@/features/feed/useHideOnScroll";
import {
  useInfiniteFeed,
  useScrollSentinel,
} from "@/features/feed/useInfiniteFeed";
import { SubjectItem, fetchSyllabus } from "@/lib/api";

const CARD_TYPES = [
  { value: "all", label: "All" },
  { value: "TRAP", label: "Traps" },
  { value: "FORMULA", label: "Formulas" },
  { value: "CONCEPT", label: "Concepts" },
  { value: "SHORTCUT", label: "Shortcuts" },
];

/** Exit animation length; must match the card's transition duration. */
const LEAVE_MS = 260;

export default function FeedPage() {
  const [subjects, setSubjects] = useState<SubjectItem[]>([]);
  const [subjectSlug, setSubjectSlug] = useState("all");
  const [cardType, setCardType] = useState("all");
  const [leaving, setLeaving] = useState<Set<number>>(new Set());

  const { cards, loading, loadingMore, error, total, hasMore, loadMore, dismiss } =
    useInfiniteFeed(subjectSlug, cardType);

  const sentinelRef = useScrollSentinel(loadMore, hasMore && !loading);
  const headerHidden = useHideOnScroll();

  useEffect(() => {
    let cancelled = false;
    fetchSyllabus()
      .then((data) => !cancelled && setSubjects(data))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  // Fade the card out first, then remove it, so the grid does not jump.
  const handleMastered = useCallback(
    (id: number) => {
      setLeaving((prev) => new Set(prev).add(id));
      window.setTimeout(() => {
        void dismiss(id);
        setLeaving((prev) => {
          const next = new Set(prev);
          next.delete(id);
          return next;
        });
      }, LEAVE_MS);
    },
    [dismiss],
  );

  const chipStyle = (active: boolean) => ({
    background: active ? "var(--accent)" : "var(--surface)",
    border: "var(--line-width) solid var(--line)",
    color: "var(--ink)",
    boxShadow: active ? "var(--shadow-sm)" : "none",
  });

  return (
    <div className="space-y-3">
      {/* Sticky controls that slide away on scroll down and return on scroll
          up, so the cards get the full screen while reading. */}
      <div
        className="sticky top-0 z-20 -mx-4 px-4 py-2 transition-transform duration-200 md:-mx-8 md:px-8"
        style={{
          background: "var(--canvas)",
          transform: headerHidden ? "translateY(-110%)" : "translateY(0)",
        }}
      >
        <div className="flex items-center gap-2 overflow-x-auto pb-1">
          <select
            value={subjectSlug}
            onChange={(e) => setSubjectSlug(e.target.value)}
            aria-label="Filter by subject"
            className="min-h-10 shrink-0 rounded-[var(--radius-pill)] px-3 text-[11px] font-bold"
            style={chipStyle(subjectSlug !== "all")}
          >
            <option value="all">All subjects</option>
            {subjects.map((s) => (
              <option key={s.slug} value={s.slug}>
                {s.name}
              </option>
            ))}
          </select>

          {CARD_TYPES.map((t) => (
            <button
              key={t.value}
              type="button"
              onClick={() => setCardType(t.value)}
              className="min-h-10 shrink-0 rounded-[var(--radius-pill)] px-3 text-[11px] font-bold"
              style={chipStyle(cardType === t.value)}
            >
              {t.label}
            </button>
          ))}

          <span
            className="ml-auto shrink-0 pl-2 text-[11px] font-bold"
            style={{ color: "var(--ink-faint)" }}
          >
            {total}
          </span>
        </div>
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
          Nothing left here. Switch filters or refresh.
        </p>
      ) : (
        /* CSS columns pack cards by height with no row gaps, which is what
           makes the layout read as a masonry wall rather than a grid. */
        <div className="columns-1 gap-4 sm:columns-2 lg:columns-3 2xl:columns-4">
          {cards.map((card) => (
            <FeedCard
              key={card.id}
              card={card}
              leaving={leaving.has(card.id)}
              onMastered={handleMastered}
            />
          ))}
        </div>
      )}

      {hasMore && !loading && <div ref={sentinelRef} aria-hidden className="h-px" />}

      {loadingMore && (
        <p className="flex items-center justify-center gap-2 py-5 text-xs font-semibold" style={{ color: "var(--ink-faint)" }}>
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading more...
        </p>
      )}

      {!hasMore && cards.length > 0 && (
        <p className="py-5 text-center text-xs font-semibold" style={{ color: "var(--ink-faint)" }}>
          That is everything for this filter.
        </p>
      )}
    </div>
  );
}
