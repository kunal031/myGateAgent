"use client";

import React, { useEffect, useState } from "react";
import { ChevronRight, Loader2, RotateCcw, Sparkles, Wrench } from "lucide-react";

import { ConceptRollup, fetchConceptRollup } from "@/lib/api";

type View = "fix" | "learned" | "revised";

const VIEWS: { key: View; label: string; icon: typeof Wrench; blurb: string }[] = [
  { key: "fix", label: "What to fix", icon: Wrench,
    blurb: "Untouched or still learning" },
  { key: "learned", label: "Learned", icon: Sparkles,
    blurb: "Marked learned or better" },
  { key: "revised", label: "Revised", icon: RotateCcw,
    blurb: "Been back over at least once" },
];

/**
 * Concepts in one state, grouped Subject -> Chapter -> Topic.
 *
 * The drill-down beside this answers "how am I doing in Operating
 * Systems". This answers the other direction -- "where are the concepts
 * I still have to fix" -- over the same hierarchy, which is the question
 * that decides what to open next.
 *
 * Subjects are collapsed by default and ordered by exam weight, because
 * with nothing marked yet the fix list is all 282 concepts: an expanded
 * worklist that long is not a worklist.
 */
export default function ConceptRollupPanel() {
  const [view, setView] = useState<View>("fix");
  const [data, setData] = useState<ConceptRollup | null>(null);
  const [failed, setFailed] = useState(false);
  const [open, setOpen] = useState<Set<string>>(new Set());

  useEffect(() => {
    let cancelled = false;
    fetchConceptRollup(view)
      .then((rows) => { if (!cancelled) { setData(rows); setFailed(false); } })
      .catch(() => { if (!cancelled) { setData(null); setFailed(true); } });
    return () => { cancelled = true; };
  }, [view]);

  // Derived rather than a third piece of state: the panel is loading
  // exactly when the data in hand is not the view that was asked for.
  // Setting a loading flag synchronously in the effect above is what
  // triggers a cascading render.
  const loading = !failed && data?.view !== view;

  const toggle = (key: string) =>
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  const active = VIEWS.find((v) => v.key === view);

  return (
    <section className="overflow-hidden rounded-[var(--radius-lg)]"
             style={{
               background: "var(--surface)",
               border: "var(--line-width) solid var(--line)",
             }}>
      <header className="flex flex-wrap items-center gap-2 px-3 py-2.5">
        <h3 className="mr-auto text-[13px] font-bold" style={{ color: "var(--ink)" }}>
          Concepts
          {data && (
            <span className="ml-1.5 text-[11px] font-normal"
                  style={{ color: "var(--ink-faint)" }}>
              {data.total}
            </span>
          )}
        </h3>

        <div className="flex gap-1 rounded-[var(--radius-pill)] p-0.5"
             style={{
               background: "var(--surface-sunk)",
               border: "var(--line-width) solid var(--line)",
             }}>
          {VIEWS.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              type="button"
              onClick={() => { setView(key); setOpen(new Set()); }}
              title={VIEWS.find((v) => v.key === key)?.blurb}
              className="flex items-center gap-1 rounded-[var(--radius-pill)] px-2.5 py-1 text-[11px] font-bold"
              style={view === key
                ? { background: "var(--accent)", color: "var(--ink)" }
                : { background: "transparent", color: "var(--ink-faint)" }}
            >
              <Icon className="h-3 w-3" />
              {label}
            </button>
          ))}
        </div>
      </header>

      {active && (
        <p className="px-3 pb-2 text-[10px]" style={{ color: "var(--ink-faint)" }}>
          {active.blurb}
        </p>
      )}

      {loading && (
        <div className="flex justify-center py-6">
          <Loader2 className="h-4 w-4 animate-spin"
                   style={{ color: "var(--ink-faint)" }} />
        </div>
      )}

      {!loading && data && data.total === 0 && (
        <p className="px-3 py-5 text-center text-[12px]"
           style={{ color: "var(--ink-faint)" }}>
          {view === "fix"
            ? "Nothing outstanding — every concept is marked learned."
            : `No concepts marked ${view} yet. Use the ${
                view === "learned" ? "L" : "R"
              } button on a feed card.`}
        </p>
      )}

      {!loading && data?.subjects.map((subject) => {
        const subjectKey = `s-${subject.id}`;
        const subjectOpen = open.has(subjectKey);
        return (
          <div key={subjectKey}>
            <button
              type="button"
              onClick={() => toggle(subjectKey)}
              className="flex w-full items-center gap-2 px-3 py-2 text-left hover:opacity-80"
              style={{ borderTop: "var(--line-width) solid var(--line)" }}
            >
              <ChevronRight className="h-3.5 w-3.5 shrink-0 transition-transform"
                            style={{
                              color: "var(--ink-faint)",
                              transform: subjectOpen ? "rotate(90deg)" : "none",
                            }} />
              <span className="min-w-0 flex-1 truncate text-[12px] font-bold"
                    style={{ color: "var(--ink)" }}>
                {subject.name}
                <span className="ml-1.5 text-[10px] font-normal"
                      style={{ color: "var(--ink-faint)" }}>
                  ~{subject.weight}M
                </span>
              </span>
              <span className="shrink-0 font-mono text-[11px] font-bold"
                    style={{ color: "var(--ink-soft)" }}>
                {subject.count}
              </span>
            </button>

            {subjectOpen && subject.children?.map((chapter) => {
              const chapterKey = `c-${subject.id}-${chapter.id}`;
              const chapterOpen = open.has(chapterKey);
              return (
                <div key={chapterKey}>
                  <button
                    type="button"
                    onClick={() => toggle(chapterKey)}
                    className="flex w-full items-center gap-2 py-1.5 pr-3 text-left hover:opacity-80"
                    style={{
                      paddingLeft: "28px",
                      background: "var(--surface-sunk)",
                      borderTop: "var(--line-width) solid var(--line)",
                    }}
                  >
                    <ChevronRight className="h-3 w-3 shrink-0 transition-transform"
                                  style={{
                                    color: "var(--ink-faint)",
                                    transform: chapterOpen ? "rotate(90deg)" : "none",
                                  }} />
                    <span className="min-w-0 flex-1 truncate text-[11px] font-semibold"
                          style={{ color: "var(--ink-soft)" }}>
                      {chapter.name}
                    </span>
                    <span className="shrink-0 font-mono text-[10px]"
                          style={{ color: "var(--ink-faint)" }}>
                      {chapter.count}
                    </span>
                  </button>

                  {chapterOpen && chapter.children?.map((topic) => (
                    <div key={`t-${topic.id}`}>
                      <p className="py-1 pr-3 text-[10px] font-bold uppercase tracking-wider"
                         style={{
                           paddingLeft: "44px",
                           color: "var(--ink-faint)",
                           background: "var(--surface-sunk)",
                           borderTop: "var(--line-width) solid var(--line)",
                         }}>
                        {topic.name}
                      </p>
                      {topic.concepts?.map((concept) => (
                        <div key={`k-${concept.id}`}
                             className="flex items-center gap-2 py-1.5 pr-3"
                             style={{
                               paddingLeft: "56px",
                               background: "var(--surface-sunk)",
                               borderTop: "var(--line-width) solid var(--line)",
                             }}>
                          <span className="min-w-0 flex-1 truncate text-[11px]"
                                style={{ color: "var(--ink-soft)" }}>
                            {concept.name}
                          </span>
                          {(concept.revisions ?? 0) > 0 && (
                            <span className="shrink-0 font-mono text-[10px]"
                                  style={{ color: "var(--ink-faint)" }}
                                  title={`revised ${concept.revisions} time(s)`}>
                              &times;{concept.revisions}
                            </span>
                          )}
                          <span className="shrink-0 font-mono text-[10px]"
                                style={{ color: "var(--ink-faint)" }}>
                            {concept.weight}w
                          </span>
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
        );
      })}
    </section>
  );
}
