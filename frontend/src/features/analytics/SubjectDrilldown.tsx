"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  ChevronRight, CircleCheck, CircleDashed, CircleDot, Loader2,
} from "lucide-react";

import {
  BreakdownNode, fetchBreakdown, fetchBreakdownChildren,
} from "@/lib/api";

/**
 * Subject -> Chapter -> Topic -> Concept, expanded one level at a time.
 *
 * One recursive component, because every level returns the same node
 * shape. A node carries its own `level` and `id`, so expanding anything
 * is the same call at any depth and adding a fifth level would need no
 * new component, type or fetch.
 *
 * Children are fetched when a row is opened rather than up front: the
 * whole tree is 11 subjects, 39 chapters, 57 topics and 282 concepts, and
 * loading all of it to render eleven rows spends the request on data that
 * will not be looked at. Each node caches its own children, so collapsing
 * and reopening does not refetch -- a tree is explored by opening and
 * closing, and refetching every toggle makes it feel broken.
 */

const ACCURACY_GOOD = 75;
const ACCURACY_FAIR = 50;

const STATUS_ICON: Record<string, typeof CircleDot> = {
  not_started: CircleDashed,
  learning: CircleDot,
  learned: CircleCheck,
  revised: CircleCheck,
  mastered: CircleCheck,
};

function accuracyColour(accuracy: number | null): string {
  if (accuracy === null) return "var(--ink-faint)";
  if (accuracy >= ACCURACY_GOOD) return "var(--ok, #10b981)";
  if (accuracy >= ACCURACY_FAIR) return "var(--warn, #f59e0b)";
  return "var(--bad, #f43f5e)";
}

/**
 * The metrics every row shows.
 *
 * Coverage sits beside accuracy because either alone misleads: 100% of
 * three questions is not mastery, and 20 attempts at 40% is not progress.
 *
 * The unit is labelled on every row -- "Q" for questions, "cards" for a
 * concept -- because the concept level cannot count questions at all: no
 * question carries a concept id. Without the label a topic reading 7/51
 * sits directly above concepts reading 0/6 and looks like broken
 * arithmetic, when the two are simply counting different things.
 */
function Metrics({ node }: { node: BreakdownNode }) {
  const isConcept = node.level === "concept";
  const done = isConcept ? node.cards_seen : node.covered;
  const total = isConcept ? node.cards : node.available;

  const rightValue = isConcept
    ? (node.coverage > 0 ? `${node.coverage}%` : "—")
    : (node.accuracy === null ? "—" : `${node.accuracy}%`);

  const rightColour = isConcept
    ? (node.coverage >= 100 ? "var(--ok, #10b981)"
      : node.coverage > 0 ? "var(--warn, #f59e0b)"
      : "var(--ink-faint)")
    : accuracyColour(node.accuracy);

  const Icon = STATUS_ICON[node.status] ?? null;

  return (
    <div className="flex shrink-0 items-center gap-3 text-[11px]">
      <span className="hidden font-mono sm:inline"
            style={{ color: "var(--ink-faint)" }}
            title={isConcept
              ? `${done} of ${total} cards read`
              : `${done} of ${total} questions seen`}>
        {done}/{total}
        <span style={{ opacity: 0.7 }}>{isConcept ? " cards" : "Q"}</span>
        {node.repeats > 0 && (
          <span title={`${node.repeats} repeat attempt(s)`}> +{node.repeats}</span>
        )}
        {isConcept && node.cards_mastered > 0 && (
          <span title={`${node.cards_mastered} mastered`}>
            {" "}&#9733;{node.cards_mastered}
          </span>
        )}
      </span>

      <div className="hidden h-1 w-16 overflow-hidden rounded-full sm:block"
           style={{ background: "var(--surface-sunk)" }}
           title={`${node.coverage}% covered`}>
        <div className="h-full" style={{
          width: `${Math.min(node.coverage, 100)}%`,
          background: "var(--ink-faint)",
        }} />
      </div>

      <span className="w-12 text-right font-mono font-bold"
            style={{ color: rightColour }}>
        {rightValue}
      </span>

      {Icon && (
        <Icon className="h-3.5 w-3.5 shrink-0"
              style={{
                color: node.status === "not_started"
                  ? "var(--ink-faint)" : "var(--ok, #10b981)",
              }} />
      )}
    </div>
  );
}

/** What the row says beside its name, which differs by level. */
function metaFor(node: BreakdownNode): string | undefined {
  if (node.level === "subject") return `~${node.weight}M`;
  if (node.level === "concept") return node.weight ? `${node.weight}w` : undefined;
  return node.children > 0
    ? `${node.children} ${node.level === "chapter" ? "topics" : "concepts"}`
    : undefined;
}

function Node({ node, depth }: { node: BreakdownNode; depth: number }) {
  const [open, setOpen] = useState(false);
  const [children, setChildren] = useState<BreakdownNode[] | null>(null);
  const [loading, setLoading] = useState(false);

  const expandable = node.expandable && node.id !== null;

  const toggle = useCallback(() => {
    if (!expandable) return;
    setOpen((wasOpen) => {
      if (!wasOpen && children === null && !loading) {
        setLoading(true);
        fetchBreakdownChildren(node.level, node.id as number)
          .then(setChildren)
          .catch(() => setChildren([]))
          .finally(() => setLoading(false));
      }
      return !wasOpen;
    });
  }, [children, expandable, loading, node.id, node.level]);

  const meta = metaFor(node);
  const Tag = expandable ? "button" : "div";

  return (
    <>
      <Tag
        {...(expandable ? { type: "button" as const, onClick: toggle } : {})}
        className="flex w-full items-center gap-2 px-3 py-2 text-left hover:opacity-80"
        style={{
          paddingLeft: `${12 + depth * 16}px`,
          borderTop: "var(--line-width) solid var(--line)",
          background: depth === 0 ? "transparent" : "var(--surface-sunk)",
        }}
      >
        {expandable ? (
          <ChevronRight className="h-3.5 w-3.5 shrink-0 transition-transform"
                        style={{
                          color: "var(--ink-faint)",
                          transform: open ? "rotate(90deg)" : "none",
                        }} />
        ) : (
          <span className="w-3.5 shrink-0" />
        )}

        <span className="min-w-0 flex-1 truncate text-[12px]"
              style={{
                color: expandable ? "var(--ink)" : "var(--ink-soft)",
                fontWeight: depth === 0 ? 700 : 500,
              }}>
          {node.name}
          {meta && (
            <span className="ml-1.5 text-[10px] font-normal"
                  style={{ color: "var(--ink-faint)" }}>
              {meta}
            </span>
          )}
        </span>

        <Metrics node={node} />
      </Tag>

      {open && (loading ? (
        <div className="flex justify-center py-3">
          <Loader2 className="h-3.5 w-3.5 animate-spin"
                   style={{ color: "var(--ink-faint)" }} />
        </div>
      ) : children && children.length === 0 ? (
        <p className="py-2 text-[11px]"
           style={{
             paddingLeft: `${44 + depth * 16}px`,
             color: "var(--ink-faint)",
             borderTop: "var(--line-width) solid var(--line)",
           }}>
          Nothing recorded here yet.
        </p>
      ) : (
        children?.map((child) => (
          <Node key={`${child.level}-${child.id}`} node={child} depth={depth + 1} />
        ))
      ))}
    </>
  );
}

export default function SubjectDrilldown() {
  const [subjects, setSubjects] = useState<BreakdownNode[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    fetchBreakdown()
      .then((rows) => !cancelled && setSubjects(rows))
      .catch((err) => !cancelled
        && setError(err instanceof Error ? err.message : "Could not load"));
    return () => { cancelled = true; };
  }, []);

  return (
    <section className="overflow-hidden rounded-[var(--radius-lg)]"
             style={{
               background: "var(--surface)",
               border: "var(--line-width) solid var(--line)",
             }}>
      <header className="flex items-baseline justify-between gap-2 px-3 py-2.5">
        <h3 className="text-[13px] font-bold" style={{ color: "var(--ink)" }}>
          Subject breakdown
        </h3>
        <p className="text-[10px]" style={{ color: "var(--ink-faint)" }}>
          questions seen · accuracy · concepts in cards
        </p>
      </header>

      {error && (
        <p className="px-3 py-3 text-[12px]" style={{ color: "var(--ink-faint)" }}>
          {error}
        </p>
      )}

      {!subjects && !error && (
        <div className="flex justify-center py-6">
          <Loader2 className="h-4 w-4 animate-spin"
                   style={{ color: "var(--ink-faint)" }} />
        </div>
      )}

      {subjects?.map((subject) => (
        <Node key={`subject-${subject.id}`} node={subject} depth={0} />
      ))}
    </section>
  );
}
