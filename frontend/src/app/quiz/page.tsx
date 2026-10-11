"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Play, Target, Plus } from "lucide-react";

import SessionHistory from "@/features/exam/SessionHistory";
import PaperImporter from "@/features/papers/PaperImporter";
import { QuestionPaper, fetchPapers } from "@/lib/papers";
import {
  ExamPatterns, SubjectItem, fetchExamPatterns, fetchSyllabus, startExam,
} from "@/lib/api";

const TYPES = [
  { value: "all", label: "All types" },
  { value: "MCQ", label: "MCQ" },
  { value: "MSQ", label: "MSQ" },
  { value: "NAT", label: "NAT" },
];
const COUNTS = [5, 10, 15, 20, 30];
const DURATIONS = [5, 10, 15, 20, 30, 45];

export default function QuizPage() {
  const router = useRouter();
  const [patterns, setPatterns] = useState<ExamPatterns | null>(null);
  const [syllabus, setSyllabus] = useState<SubjectItem[]>([]);
  const [subject, setSubject] = useState("");
  const [topic, setTopic] = useState("all");
  const [type, setType] = useState("all");
  const [count, setCount] = useState(10);
  const [minutes, setMinutes] = useState(15);
  const [starting, setStarting] = useState(false);
  const [papers, setPapers] = useState<QuestionPaper[]>([]);
  const [paperId, setPaperId] = useState("all");
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchExamPatterns(), fetchSyllabus()])
      .then(([p, s]) => {
        if (cancelled) return;
        setPatterns(p);
        setSyllabus(s);
        const first = p.subjects.find((x) => x.question_count > 0);
        if (first) setSubject(first.slug);
      })
      .catch(() => !cancelled && setError("Could not load quiz options."));
    return () => { cancelled = true; };
  }, []);

  // Papers follow the subject and topic, so the picker only offers ones
  // whose questions the current filters would actually include.
  // Papers follow the subject and topic, so the picker only offers ones
  // whose questions the current filters would include. `paperNonce` lets an
  // import re-run this without duplicating the fetch.
  const [paperNonce, setPaperNonce] = useState(0);
  const reloadPapers = useCallback(() => setPaperNonce((n) => n + 1), []);

  useEffect(() => {
    if (!subject) return;
    let cancelled = false;
    fetchPapers({ subjectSlug: subject, topicSlug: topic })
      .then((rows) => !cancelled && setPapers(rows))
      .catch(() => {});
    return () => { cancelled = true; };
  }, [subject, topic, paperNonce]);

  /** Re-read the per-subject question counts after an import changes them. */
  const refreshPatterns = useCallback(async () => {
    try {
      const fresh = await fetchExamPatterns();
      setPatterns(fresh);
    } catch {
      // The chips keep their previous counts; nothing is broken by that.
    }
  }, []);

  const available = useMemo(
    () => (patterns?.subjects ?? []).filter((s) => s.question_count > 0),
    [patterns],
  );

  const topics = useMemo(
    () => syllabus.find((s) => s.slug === subject)?.topics ?? [],
    [syllabus, subject],
  );

  const launch = async () => {
    setStarting(true);
    setError(null);
    try {
      const session = await startExam({
        kind: "quiz",
        pattern: topic === "all" ? "subject" : "topic",
        subject_slug: subject,
        topic_slug: topic === "all" ? undefined : topic,
        question_type: type,
        questions: count,
        duration_minutes: minutes,
      });
      router.push(`/quiz/${session.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start the quiz.");
      setStarting(false);
    }
  };

  const chip = (active: boolean) => ({
    background: active ? "var(--accent)" : "var(--surface)",
    border: "var(--line-width) solid var(--line)",
    color: "var(--ink)",
    boxShadow: active ? "var(--shadow-sm)" : "none",
  });

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-lg font-extrabold sm:text-xl" style={{ color: "var(--ink)" }}>
          Quiz Drill
        </h1>
        <p className="text-[11px] font-semibold" style={{ color: "var(--ink-faint)" }}>
          Short practice with the answer and explanation after each question.
        </p>
      </header>

      {error && (
        <p className="rounded-[var(--radius)] px-4 py-3 text-xs font-semibold"
           style={{ background: "var(--danger)", color: "var(--ink)",
                    border: "var(--line-width) solid var(--line)" }}>
          {error}
        </p>
      )}

      <section className="space-y-4 rounded-[var(--radius-lg)] p-4"
               style={{ background: "var(--surface)",
                        border: "var(--line-width) solid var(--line)",
                        boxShadow: "var(--shadow-sm)" }}>
        <div className="space-y-2">
          <p className="text-[10px] font-extrabold uppercase tracking-wider"
             style={{ color: "var(--ink-faint)" }}>Subject</p>
          <div className="flex flex-wrap gap-2">
            {available.map((s) => (
              <button key={s.slug} type="button"
                      onClick={() => { setSubject(s.slug); setTopic("all"); }}
                      className="min-h-10 rounded-[var(--radius-pill)] px-3 text-[11px] font-bold"
                      style={chip(subject === s.slug)}>
                {s.name} <span style={{ color: "var(--ink-faint)" }}>({s.question_count})</span>
              </button>
            ))}
          </div>
        </div>

        <div className="flex flex-wrap items-end gap-3">
          {topics.length > 0 && (
            <div className="min-w-0 space-y-2">
              <p className="text-[10px] font-extrabold uppercase tracking-wider"
                 style={{ color: "var(--ink-faint)" }}>Topic</p>
              <select
                value={topic}
                onChange={(e) => { setTopic(e.target.value); setPaperId("all"); }}
                aria-label="Topic"
                className="min-h-10 w-full rounded-[var(--radius-pill)] px-3 text-[11px] font-bold sm:w-auto"
                style={chip(topic !== "all")}
              >
                <option value="all">Whole subject</option>
                {topics.map((t) => (
                  <option key={t.slug} value={t.slug}>{t.name}</option>
                ))}
              </select>
            </div>
          )}

          {/* Papers for the chosen subject and topic, so a drill can be
              scoped to one imported set rather than the whole bank. */}
          <div className="min-w-0 space-y-2">
            <p className="text-[10px] font-extrabold uppercase tracking-wider"
               style={{ color: "var(--ink-faint)" }}>Question paper</p>
            <select
              value={paperId}
              onChange={(e) => setPaperId(e.target.value)}
              aria-label="Question paper"
              disabled={papers.length === 0}
              className="min-h-10 w-full rounded-[var(--radius-pill)] px-3 text-[11px] font-bold disabled:opacity-50 sm:w-auto"
              style={chip(paperId !== "all")}
            >
              <option value="all">
                {papers.length ? "Any paper" : "No papers yet"}
              </option>
              {papers.map((pp) => (
                <option key={pp.id} value={String(pp.id)}>
                  {pp.name.slice(0, 48)} ({pp.question_count})
                </option>
              ))}
            </select>
          </div>

          <button
            type="button"
            onClick={() => setImporting(true)}
            className="flex min-h-10 items-center gap-1 rounded-[var(--radius-pill)] px-3 text-[11px] font-bold"
            style={{ background: "var(--accent)", color: "var(--ink)",
                     border: "var(--line-width) solid var(--line)" }}
          >
            <Plus className="h-3.5 w-3.5" />
            Add paper
          </button>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <div className="space-y-2">
            <p className="text-[10px] font-extrabold uppercase tracking-wider"
               style={{ color: "var(--ink-faint)" }}>Question type</p>
            <div className="flex flex-wrap gap-2">
              {TYPES.map((t) => (
                <button key={t.value} type="button" onClick={() => setType(t.value)}
                        className="min-h-10 rounded-[var(--radius-pill)] px-3 text-[11px] font-bold"
                        style={chip(type === t.value)}>{t.label}</button>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <p className="text-[10px] font-extrabold uppercase tracking-wider"
               style={{ color: "var(--ink-faint)" }}>Questions</p>
            <div className="flex flex-wrap gap-2">
              {COUNTS.map((n) => (
                <button key={n} type="button" onClick={() => setCount(n)}
                        className="min-h-10 rounded-[var(--radius-pill)] px-3.5 text-[11px] font-bold"
                        style={chip(count === n)}>{n}</button>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <p className="text-[10px] font-extrabold uppercase tracking-wider"
               style={{ color: "var(--ink-faint)" }}>Minutes</p>
            <div className="flex flex-wrap gap-2">
              {DURATIONS.map((n) => (
                <button key={n} type="button" onClick={() => setMinutes(n)}
                        className="min-h-10 rounded-[var(--radius-pill)] px-3.5 text-[11px] font-bold"
                        style={chip(minutes === n)}>{n}</button>
              ))}
            </div>
          </div>
        </div>

        <button
          type="button"
          onClick={launch}
          disabled={starting || !subject}
          className="flex min-h-12 w-full items-center justify-center gap-2 rounded-[var(--radius-pill)] text-sm font-extrabold disabled:opacity-50 sm:w-auto sm:px-8"
          style={{ background: "var(--accent)", color: "var(--ink)",
                   border: "var(--line-width) solid var(--line)",
                   boxShadow: "var(--shadow)" }}
        >
          <Play className="h-4 w-4" />
          {starting ? "Preparing questions..." : "Start quiz"}
        </button>

        {patterns && (
          <p className="flex items-center gap-1.5 text-[11px] font-semibold"
             style={{ color: "var(--ink-faint)" }}>
            <Target className="h-3.5 w-3.5" />
            {patterns.total_questions_available} questions in the bank.
          </p>
        )}
      </section>

      {importing && (
        <PaperImporter
          subjects={syllabus}
          onClose={() => setImporting(false)}
          onImported={() => { reloadPapers(); void refreshPatterns(); }}
        />
      )}

      <SessionHistory
        kind="quiz"
        subjects={available}
        resultHref={(id) => `/quiz/${id}/result`}
        resumeHref={(id) => `/quiz/${id}`}
      />
    </div>
  );
}
