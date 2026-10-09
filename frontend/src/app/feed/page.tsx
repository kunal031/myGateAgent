"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Loader2 } from "lucide-react";

import AssistantBar from "@/features/assistant/AssistantBar";
import ChatPanel from "@/features/assistant/ChatPanel";
import FeedCard from "@/features/feed/FeedCard";
import { useHideOnScroll } from "@/features/feed/useHideOnScroll";
import {
  useInfiniteFeed, useScrollSentinel,
} from "@/features/feed/useInfiniteFeed";
import {
  AssistantLanguage, FeedCardItem, FeedFilters, SubjectItem,
  askAssistant, fetchSyllabus, markCardRecalled,
} from "@/lib/api";

const MODES = [
  { value: "all", label: "All" },
  { value: "BASIC", label: "Basic" },
  { value: "ADVANCED", label: "Advanced" },
  { value: "REVISION", label: "Revision" },
];

const CARD_TYPES = [
  { value: "all", label: "All types" },
  { value: "TRAP", label: "Traps" },
  { value: "FORMULA", label: "Formulas" },
  { value: "CONCEPT", label: "Concepts" },
  { value: "SHORTCUT", label: "Shortcuts" },
];

/** Exit animation length; matches the card's transition duration. */
const LEAVE_MS = 260;

export default function FeedPage() {
  const [subjects, setSubjects] = useState<SubjectItem[]>([]);
  const [subjectSlug, setSubjectSlug] = useState("all");
  const [topicSlug, setTopicSlug] = useState("all");
  const [cardType, setCardType] = useState("all");
  const [mode, setMode] = useState("all");
  const [leaving, setLeaving] = useState<Set<number>>(new Set());
  const [threadId, setThreadId] = useState<number | null>(null);
  // The card Explain was pressed on. Set before the request goes out so the
  // modal can open at once showing the card, rather than after the answer
  // lands several seconds later.
  const [explainCard, setExplainCard] = useState<FeedCardItem | null>(null);
  const [explainPending, setExplainPending] = useState(false);
  const [language, setLanguage] = useState<AssistantLanguage>("en");

  const filters: FeedFilters = useMemo(
    () => ({ subjectSlug, topicSlug, cardType, mode }),
    [subjectSlug, topicSlug, cardType, mode],
  );

  const { cards, loading, loadingMore, error, total, hasMore, loadMore, dismiss } =
    useInfiniteFeed(filters);

  const sentinelRef = useScrollSentinel(loadMore, hasMore && !loading);
  const headerHidden = useHideOnScroll();

  useEffect(() => {
    let cancelled = false;
    fetchSyllabus()
      .then((data) => !cancelled && setSubjects(data))
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const topics = useMemo(
    () => subjects.find((s) => s.slug === subjectSlug)?.topics ?? [],
    [subjects, subjectSlug],
  );

  // Fade the card out, record the recall, then remove it so the columns
  // reflow rather than snapping.
  const handleMastered = useCallback(
    (id: number) => {
      setLeaving((prev) => new Set(prev).add(id));
      void markCardRecalled(id).catch(() => {});
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

  const handleExplain = useCallback(
    async (card: FeedCardItem) => {
      // Open first, answer second: the request takes seconds, and the
      // student should see the modal respond to their click immediately.
      setExplainCard(card);
      setExplainPending(true);
      setThreadId(null);
      try {
        const result = await askAssistant({
          query: `Explain this: ${card.title}`,
          card_id: card.id,
          language,
        });
        if (result.output === "chat") setThreadId(result.thread_id);
      } catch {
        // The modal stays open with the card showing, so a failure leaves
        // the student somewhere they can retype the question rather than
        // closing on them.
      } finally {
        setExplainPending(false);
      }
    },
    [language],
  );

  const closeChat = useCallback(() => {
    setThreadId(null);
    setExplainCard(null);
    setExplainPending(false);
  }, []);

  const chip = (active: boolean) => ({
    background: active ? "var(--accent)" : "var(--surface)",
    border: "var(--line-width) solid var(--line)",
    color: "var(--ink)",
    boxShadow: active ? "var(--shadow-sm)" : "none",
  });

  return (
    <div className="space-y-3">
      <div
        className="sticky top-0 z-20 -mx-4 space-y-2 px-4 py-2 transition-transform duration-200 md:-mx-6 md:px-6"
        style={{
          background: "var(--canvas)",
          transform: headerHidden ? "translateY(-110%)" : "translateY(0)",
        }}
      >
        <AssistantBar
          onFilters={(f) => {
            if (f.subjectSlug) { setSubjectSlug(f.subjectSlug); setTopicSlug("all"); }
            if (f.cardType) setCardType(f.cardType);
            if (f.mode) setMode(f.mode);
          }}
          onChat={setThreadId}
          language={language}
          onLanguageChange={setLanguage}
        />

        <div className="flex items-center gap-2 overflow-x-auto pb-1">
          <select
            value={subjectSlug}
            onChange={(e) => { setSubjectSlug(e.target.value); setTopicSlug("all"); }}
            aria-label="Subject"
            className="min-h-10 shrink-0 rounded-[var(--radius-pill)] px-3 text-[11px] font-bold"
            style={chip(subjectSlug !== "all")}
          >
            <option value="all">All subjects</option>
            {subjects.map((s) => (
              <option key={s.slug} value={s.slug}>{s.name}</option>
            ))}
          </select>

          {topics.length > 0 && (
            <select
              value={topicSlug}
              onChange={(e) => setTopicSlug(e.target.value)}
              aria-label="Topic"
              className="min-h-10 shrink-0 rounded-[var(--radius-pill)] px-3 text-[11px] font-bold"
              style={chip(topicSlug !== "all")}
            >
              <option value="all">All topics</option>
              {topics.map((t) => (
                <option key={t.slug} value={t.slug}>{t.name}</option>
              ))}
            </select>
          )}

          {MODES.map((m) => (
            <button key={m.value} type="button" onClick={() => setMode(m.value)}
                    className="min-h-10 shrink-0 rounded-[var(--radius-pill)] px-3 text-[11px] font-bold"
                    style={chip(mode === m.value)}>
              {m.label}
            </button>
          ))}

          <select
            value={cardType}
            onChange={(e) => setCardType(e.target.value)}
            aria-label="Card type"
            className="min-h-10 shrink-0 rounded-[var(--radius-pill)] px-3 text-[11px] font-bold"
            style={chip(cardType !== "all")}
          >
            {CARD_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>

          <span className="ml-auto shrink-0 pl-2 text-[11px] font-bold"
                style={{ color: "var(--ink-faint)" }}>
            {total}
          </span>
        </div>
      </div>

      {(threadId !== null || explainCard !== null) && (
        <ChatPanel
          threadId={threadId}
          language={language}
          card={explainCard}
          pending={explainPending}
          onClose={closeChat}
        />
      )}

      {error && (
        <p className="rounded-[var(--radius)] px-4 py-3 text-xs font-semibold"
           style={{ background: "var(--danger)", color: "var(--ink)",
                    border: "var(--line-width) solid var(--line)" }}>
          {error}
        </p>
      )}

      {loading ? (
        <p className="py-16 text-center text-xs font-semibold" style={{ color: "var(--ink-faint)" }}>
          Loading cards...
        </p>
      ) : cards.length === 0 ? (
        <p className="rounded-[var(--radius-lg)] py-14 text-center text-xs font-semibold"
           style={{ background: "var(--surface)", color: "var(--ink-faint)",
                    border: "var(--line-width) solid var(--line)" }}>
          Nothing here yet. Ask the assistant above for a topic.
        </p>
      ) : (
        <div className="columns-1 gap-4 sm:columns-2 lg:columns-3 2xl:columns-4">
          {cards.map((card) => (
            <FeedCard
              key={card.id}
              card={card}
              leaving={leaving.has(card.id)}
              onMastered={handleMastered}
              onExplain={handleExplain}
            />
          ))}
        </div>
      )}

      {hasMore && !loading && <div ref={sentinelRef} aria-hidden className="h-px" />}

      {loadingMore && (
        <p className="flex items-center justify-center gap-2 py-5 text-xs font-semibold"
           style={{ color: "var(--ink-faint)" }}>
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading more...
        </p>
      )}
    </div>
  );
}
