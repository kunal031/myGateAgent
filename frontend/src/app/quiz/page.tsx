"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Play, Target, Plus, Loader2 } from "lucide-react";

import SessionHistory from "@/features/exam/SessionHistory";
import PaperImporter from "@/features/papers/PaperImporter";
import { QuestionPaper, fetchPapers } from "@/lib/papers";

/** Imports that have not finished, and can be reopened from the quiz page. */
const UNFINISHED = new Set(["parsing", "preview", "saving"]);
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
  // Which paper the importer reopens, if it is resuming one.
  const [resumeId, setResumeId] = useState<number | null>(null);
  // Imports still running or waiting for review, across every subject, so
  // closing the dialog does not lose the way back to them.
  const [unfinished, setUnfinished] = useState<QuestionPaper[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchExamPatterns(), fetchSyllabus()])
      .then(([p, s]) => {
        if (cancelled) return;
        setPatterns(p);
        setSyllabus(s);
        // Start on a subject that can actually be drilled.
        const first = p.subjects.find((x) => x.question_count > 0)
          ?? p.subjects[0];
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

  // Unfinished imports are listed across all subjects, since one started
  // under a different subject is still worth finishing. Re-polled while any
  // is in flight so the banner reflects where it has got to.
  useEffect(() => {
    let cancelled = false;
    const load = () => {
      fetchPapers()
        .then((rows) => {
          if (cancelled) return;
          setUnfinished(rows.filter((p) => UNFINISHED.has(p.import_status)));
        })
        .catch(() => {});
    };
    load();
    const timer = window.setInterval(load, 5000);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [paperNonce]);

  /** Re-read the per-subject question counts after an import changes them. */
  const refreshPatterns = useCallback(async () => {
    try {
      const fresh = await fetchExamPatterns();
      setPatterns(fresh);
    } catch {
      // The chips keep their previous counts; nothing is broken by that.
    }
  }, []);

  /** Questions available in the chosen subject; zero means nothing to drill. */
  const subjectQuestionCount = useMemo(
    () => (patterns?.subjects ?? []).find((s) => s.slug === subject)
      ?.question_count ?? 0,
    [patterns, subject],
  );

  const available = useMemo(
    // Every subject, including ones with no questions yet: hiding an empty
    // subject hides the place to import questions into it, which is how
    // General Aptitude stayed invisible while its four topics sat unused.
    () => patterns?.subjects ?? [],
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
                {s.name}{" "}
                <span style={{ color: "var(--ink-faint)" }}>
                  ({s.question_count})
                </span>
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
          disabled={starting || !subject || subjectQuestionCount === 0}
          className="flex min-h-12 w-full items-center justify-center gap-2 rounded-[var(--radius-pill)] text-sm font-extrabold disabled:opacity-50 sm:w-auto sm:px-8"
          style={{ background: "var(--accent)", color: "var(--ink)",
                   border: "var(--line-width) solid var(--line)",
                   boxShadow: "var(--shadow)" }}
        >
          <Play className="h-4 w-4" />
          {starting ? "Preparing questions..." : "Start quiz"}
        </button>

        {subject && subjectQuestionCount === 0 && (
          <p className="text-[11px] font-semibold"
             style={{ color: "var(--ink-faint)" }}>
            No questions in this subject yet. Use Add paper to import some.
          </p>
        )}

        {patterns && (
          <p className="flex items-center gap-1.5 text-[11px] font-semibold"
             style={{ color: "var(--ink-faint)" }}>
            <Target className="h-3.5 w-3.5" />
            {patterns.total_questions_available} questions in the bank.
          </p>
        )}
      </section>

      {unfinished.length > 0 && !importing && (
        <section className="space-y-2">
          {unfinished.map((p) => {
            const waiting = p.import_status === "preview";
            const progress = p.progress_total > 0
              ? ` ${p.progress_done}/${p.progress_total}`
              : "";
            return (
              <button
                key={p.id}
                type="button"
                onClick={() => { setResumeId(p.id); setImporting(true); }}
                className="flex w-full items-center gap-2 rounded-[var(--radius)] px-3 py-2.5 text-left"
                style={{
                  background: waiting ? "var(--warning)" : "var(--surface)",
                  border: "var(--line-width) solid var(--line)",
                  color: "var(--ink)",
                }}
              >
                {waiting
                  ? <Target className="h-4 w-4 shrink-0" />
                  : <Loader2 className="h-4 w-4 shrink-0 animate-spin" />}
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[12px] font-bold">
                    {p.name}
                  </span>
                  <span className="block text-[11px] font-semibold"
                        style={{ color: "var(--ink-faint)" }}>
                    {waiting
                      ? `${p.question_count} questions found — review and save`
                      : `${p.progress_note || "Working"}${progress}`}
                  </span>
                </span>
                <span className="shrink-0 text-[11px] font-bold">
                  {waiting ? "Review" : "View"}
                </span>
              </button>
            );
          })}
        </section>
      )}

      {importing && (
        <PaperImporter
          subjects={syllabus}
          resumePaperId={resumeId}
          onClose={() => { setImporting(false); setResumeId(null); }}
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
