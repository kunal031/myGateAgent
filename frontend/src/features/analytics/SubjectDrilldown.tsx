"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  ChevronRight, CircleDashed, CircleCheck, CircleDot, Loader2,
} from "lucide-react";

import {
  ChapterRow, ConceptRow, SubjectRow, TopicRow, fetchChapterBreakdown,
  fetchConceptBreakdown, fetchSubjectBreakdown, fetchTopicBreakdown,
} from "@/lib/api";

/**
 * Subject -> Chapter -> Topic -> Concept, expanded one level at a time.
 *
 * Each level is fetched when its row is opened rather than up front. The
 * whole tree is 11 subjects, 39 chapters, 57 topics and 282 concepts, and
 * loading it to render eleven rows would spend the request on data the
 * student will not look at.
 *
 * Results are cached per id, so collapsing and reopening a row does not
 * refetch -- a drill-down is explored by opening and closing, and
 * refetching on every toggle makes it feel broken.
 */

const ACCURACY_GOOD = 75;
const ACCURACY_FAIR = 50;

function accuracyColour(accuracy: number | null): string {
  if (accuracy === null) return "var(--ink-faint)";
  if (accuracy >= ACCURACY_GOOD) return "var(--ok, #10b981)";
  if (accuracy >= ACCURACY_FAIR) return "var(--warn, #f59e0b)";
  return "var(--bad, #f43f5e)";
}

/** Coverage and accuracy together, since either alone misleads: 100% of
 *  three questions is not mastery, and 20 attempts at 40% is not progress. */
function Metrics({ row }: { row: {
  attempted: number; correct: number; accuracy: number | null;
  available: number; covered: number; repeats: number;
} }) {
  const coverage = row.available
    ? Math.round((row.covered / row.available) * 100)
    : 0;

  return (
    <div className="flex shrink-0 items-center gap-3 text-[11px]">
      <span className="hidden font-mono sm:inline" style={{ color: "var(--ink-faint)" }}>
        {row.covered}/{row.available}
        {row.repeats > 0 && (
          <span title={`${row.repeats} repeat attempt(s)`}> +{row.repeats}</span>
        )}
      </span>

      <div className="hidden h-1 w-16 overflow-hidden rounded-full sm:block"
           style={{ background: "var(--surface-sunk)" }}
           title={`${coverage}% of questions seen`}>
        <div className="h-full" style={{
          width: `${coverage}%`, background: "var(--ink-faint)",
        }} />
      </div>

      <span className="w-12 text-right font-mono font-bold"
            style={{ color: accuracyColour(row.accuracy) }}>
        {row.accuracy === null ? "—" : `${row.accuracy}%`}
      </span>
    </div>
  );
}

function Caret({ open }: { open: boolean }) {
  return (
    <ChevronRight
      className="h-3.5 w-3.5 shrink-0 transition-transform"
      style={{
        color: "var(--ink-faint)",
        transform: open ? "rotate(90deg)" : "none",
      }}
    />
  );
}

/** One expandable row. Indentation carries the level, so the four tiers
 *  read as a tree rather than four identical lists. */
function Row({ depth, open, onToggle, label, meta, right, muted }: {
  depth: number;
  open?: boolean;
  onToggle?: () => void;
  label: string;
  meta?: string;
  right?: React.ReactNode;
  muted?: boolean;
}) {
  const Tag = onToggle ? "button" : "div";
  return (
    <Tag
      {...(onToggle ? { type: "button" as const, onClick: onToggle } : {})}
      className="flex w-full items-center gap-2 px-3 py-2 text-left hover:opacity-80"
      style={{
        paddingLeft: `${12 + depth * 16}px`,
        borderTop: "var(--line-width) solid var(--line)",
        background: depth === 0 ? "transparent" : "var(--surface-sunk)",
      }}
    >
      {onToggle ? <Caret open={!!open} /> : <span className="w-3.5 shrink-0" />}

      <span className="min-w-0 flex-1 truncate text-[12px]"
            style={{
              color: muted ? "var(--ink-faint)" : "var(--ink)",
              fontWeight: depth === 0 ? 700 : 500,
            }}>
        {label}
        {meta && (
          <span className="ml-1.5 text-[10px] font-normal"
                style={{ color: "var(--ink-faint)" }}>
            {meta}
          </span>
        )}
      </span>

      {right}
    </Tag>
  );
}

function Spinner() {
  return (
    <div className="flex justify-center py-3">
      <Loader2 className="h-3.5 w-3.5 animate-spin"
               style={{ color: "var(--ink-faint)" }} />
    </div>
  );
}

const STATUS_ICON: Record<string, typeof CircleDot> = {
  not_started: CircleDashed,
  learning: CircleDot,
  learned: CircleCheck,
  revised: CircleCheck,
  mastered: CircleCheck,
};

function Concepts({ rows }: { rows: ConceptRow[] }) {
  if (rows.length === 0) {
    return (
      <p className="px-3 py-2 text-[11px]"
         style={{ paddingLeft: "60px", color: "var(--ink-faint)",
                  borderTop: "var(--line-width) solid var(--line)" }}>
        No concepts recorded under this topic yet.
      </p>
    );
  }

  return (
    <>
      {rows.map((concept) => {
        const Icon = STATUS_ICON[concept.status] ?? CircleDashed;
        return (
          <Row
            key={concept.concept_id}
            depth={3}
            label={concept.concept_name}
            muted={concept.status === "not_started"}
            right={
              <span className="flex shrink-0 items-center gap-1.5 text-[10px]"
                    style={{ color: "var(--ink-faint)" }}>
                {concept.cards_seen > 0 && (
                  <span className="font-mono">{concept.cards_seen} seen</span>
                )}
                <Icon className="h-3.5 w-3.5"
                      style={{
                        color: concept.needs_work
                          ? "var(--ink-faint)"
                          : "var(--ok, #10b981)",
                      }} />
              </span>
            }
          />
        );
      })}
    </>
  );
}

function TopicNode({ topic }: { topic: TopicRow }) {
  const [open, setOpen] = useState(false);
  const [concepts, setConcepts] = useState<ConceptRow[] | null>(null);
  const [loading, setLoading] = useState(false);

  const toggle = useCallback(() => {
    setOpen((wasOpen) => {
      if (!wasOpen && concepts === null && !loading) {
        setLoading(true);
        fetchConceptBreakdown(topic.topic_id)
          .then(setConcepts)
          .catch(() => setConcepts([]))
          .finally(() => setLoading(false));
      }
      return !wasOpen;
    });
  }, [concepts, loading, topic.topic_id]);

  return (
    <>
      <Row
        depth={2}
        open={open}
        onToggle={toggle}
        label={topic.topic_name}
        meta={topic.concepts > 0 ? `${topic.concepts} concepts` : undefined}
        right={<Metrics row={topic} />}
      />
      {open && (loading ? <Spinner /> : <Concepts rows={concepts ?? []} />)}
    </>
  );
}

function ChapterNode({ chapter }: { chapter: ChapterRow }) {
  const [open, setOpen] = useState(false);
  const [topics, setTopics] = useState<TopicRow[] | null>(null);
  const [loading, setLoading] = useState(false);

  // A chapter with no id is the "Unassigned" bucket, which has no
  // endpoint to expand -- it exists to make a mapping gap visible.
  const expandable = chapter.chapter_id !== null;

  const toggle = useCallback(() => {
    if (!expandable) return;
    setOpen((wasOpen) => {
      if (!wasOpen && topics === null && !loading) {
        setLoading(true);
        fetchTopicBreakdown(chapter.chapter_id as number)
          .then(setTopics)
          .catch(() => setTopics([]))
          .finally(() => setLoading(false));
      }
      return !wasOpen;
    });
  }, [chapter.chapter_id, expandable, loading, topics]);

  return (
    <>
      <Row
        depth={1}
        open={open}
        onToggle={expandable ? toggle : undefined}
        label={chapter.chapter_name}
        muted={!expandable}
        right={<Metrics row={chapter} />}
      />
      {open && (loading ? <Spinner />
        : (topics ?? []).map((topic) => (
            <TopicNode key={topic.topic_id} topic={topic} />
          )))}
    </>
  );
}

function SubjectNode({ subject }: { subject: SubjectRow }) {
  const [open, setOpen] = useState(false);
  const [chapters, setChapters] = useState<ChapterRow[] | null>(null);
  const [loading, setLoading] = useState(false);

  const toggle = useCallback(() => {
    setOpen((wasOpen) => {
      if (!wasOpen && chapters === null && !loading) {
        setLoading(true);
        fetchChapterBreakdown(subject.subject_id)
          .then(setChapters)
          .catch(() => setChapters([]))
          .finally(() => setLoading(false));
      }
      return !wasOpen;
    });
  }, [chapters, loading, subject.subject_id]);

  return (
    <>
      <Row
        depth={0}
        open={open}
        onToggle={toggle}
        label={subject.subject_name}
        meta={`~${subject.weightage_marks}M`}
        right={<Metrics row={subject} />}
      />
      {open && (loading ? <Spinner />
        : (chapters ?? []).map((chapter) => (
            <ChapterNode
              key={chapter.chapter_id ?? `unassigned-${subject.subject_id}`}
              chapter={chapter}
            />
          )))}
    </>
  );
}

export default function SubjectDrilldown() {
  const [subjects, setSubjects] = useState<SubjectRow[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    fetchSubjectBreakdown()
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
          seen/total · accuracy
        </p>
      </header>

      {error && (
        <p className="px-3 py-3 text-[12px]" style={{ color: "var(--ink-faint)" }}>
          {error}
        </p>
      )}

      {!subjects && !error && <Spinner />}

      {subjects?.map((subject) => (
        <SubjectNode key={subject.subject_id} subject={subject} />
      ))}
    </section>
  );
}
