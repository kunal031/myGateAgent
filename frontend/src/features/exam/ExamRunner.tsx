"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, Clock, Flag } from "lucide-react";

import MathText from "@/components/MathText";
import {
  ExamQuestion, ExamState, ExamSummary,
  fetchExam, saveExamAnswer, submitExam, visitExamQuestion,
} from "@/lib/api";
import AnswerInput from "./AnswerInput";
import QuestionPalette from "./QuestionPalette";
import { formatClock } from "./palette";

const EMPTY_COUNTS: Record<ExamState, number> = {
  not_visited: 0, not_answered: 0, answered: 0, marked: 0, answered_marked: 0,
};

export default function ExamRunner({ examId }: { examId: number }) {
  const router = useRouter();
  const [exam, setExam] = useState<ExamSummary | null>(null);
  const [questions, setQuestions] = useState<ExamQuestion[]>([]);
  const [current, setCurrent] = useState(1);
  const [draft, setDraft] = useState("");
  const [remaining, setRemaining] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // When the current question was opened, used to report time per question.
  // Initialised lazily: calling Date.now() during render is impure, and the
  // value is only meaningful once a question is actually on screen.
  const enteredAt = useRef<number | null>(null);

  const secondsOnQuestion = () =>
    enteredAt.current === null
      ? 0
      : Math.round((Date.now() - enteredAt.current) / 1000);

  useEffect(() => {
    let cancelled = false;
    fetchExam(examId)
      .then((data) => {
        if (cancelled) return;
        setExam(data);
        setQuestions(data.questions ?? []);
        setRemaining(data.remaining_seconds);
        const resumeAt = (data.questions ?? []).find(
          (q) => q.state === "not_visited" || q.state === "not_answered",
        );
        const position = resumeAt?.position ?? 1;
        setCurrent(position);
        setDraft(resumeAt?.user_answer ?? "");
        void visitExamQuestion(examId, position);
      })
      .catch(() => !cancelled && setError("Could not load this test."));
    return () => { cancelled = true; };
  }, [examId]);

  const question = questions.find((q) => q.position === current);

  const handleSubmit = useCallback(async () => {
    setSubmitting(true);
    try {
      const result = await submitExam(examId);
      router.push(`/test/${examId}/result`);
      return result;
    } catch {
      setError("Could not submit the test.");
      setSubmitting(false);
    }
  }, [examId, router]);

  // Countdown; auto-submits when time runs out, as the real exam does.
  useEffect(() => {
    if (!exam || exam.status !== "in_progress") return;
    const timer = window.setInterval(() => {
      setRemaining((prev) => {
        if (prev <= 1) {
          window.clearInterval(timer);
          void handleSubmit();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => window.clearInterval(timer);
  }, [exam, handleSubmit]);

  const persist = useCallback(
    async (answer: string, marked?: boolean) => {
      if (!question) return;
      const spent = secondsOnQuestion();
      try {
        const saved = await saveExamAnswer(examId, question.position, {
          answer, marked, time_spent_seconds: spent,
        });
        setQuestions((prev) =>
          prev.map((q) =>
            q.position === saved.position
              ? { ...q, state: saved.state, user_answer: saved.user_answer }
              : q,
          ),
        );
      } catch {
        setError("Could not save that answer.");
      }
    },
    [examId, question],
  );

  /** Navigate to a question, loading its saved answer and marking it seen.
   *
   *  This runs from a click rather than an effect on `current`, so no state
   *  is set during render and the visit is recorded exactly once per move.
   */
  const goTo = useCallback(
    (position: number) => {
      if (position < 1 || position > questions.length) return;
      const target = questions.find((q) => q.position === position);
      setCurrent(position);
      setDraft(target?.user_answer ?? "");
      enteredAt.current = Date.now();
      void visitExamQuestion(examId, position);
      setQuestions((prev) =>
        prev.map((q) =>
          q.position === position && q.state === "not_visited"
            ? { ...q, state: "not_answered" }
            : q,
        ),
      );
    },
    [examId, questions],
  );

  const counts = questions.reduce(
    (acc, q) => ({ ...acc, [q.state]: (acc[q.state] ?? 0) + 1 }),
    { ...EMPTY_COUNTS },
  );

  if (error) {
    return (
      <p className="rounded-[var(--radius)] px-4 py-3 text-sm font-semibold"
         style={{ background: "var(--danger)", color: "var(--ink)",
                  border: "var(--line-width) solid var(--line)" }}>
        {error}
      </p>
    );
  }

  if (!exam || !question) {
    return <p className="py-16 text-center text-xs font-semibold"
              style={{ color: "var(--ink-faint)" }}>Loading test...</p>;
  }

  const lowTime = remaining < 300;

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-extrabold" style={{ color: "var(--ink)" }}>
            {exam.name}
          </h1>
          <p className="text-[11px] font-semibold" style={{ color: "var(--ink-faint)" }}>
            {exam.total_questions} questions · {exam.total_marks} marks
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span
            className="flex min-h-11 items-center gap-2 rounded-[var(--radius-pill)] px-4 font-mono text-sm font-bold"
            style={{
              background: lowTime ? "var(--danger)" : "var(--surface)",
              border: "var(--line-width) solid var(--line)",
              color: "var(--ink)",
            }}
            aria-live={lowTime ? "polite" : "off"}
          >
            <Clock className="h-4 w-4" />
            {formatClock(remaining)}
          </span>

          <button
            type="button"
            onClick={handleSubmit}
            disabled={submitting}
            className="min-h-11 rounded-[var(--radius-pill)] px-4 text-xs font-bold disabled:opacity-50"
            style={{
              background: "var(--accent)", color: "var(--ink)",
              border: "var(--line-width) solid var(--line)",
              boxShadow: "var(--shadow-sm)",
            }}
          >
            {submitting ? "Submitting..." : "Submit test"}
          </button>
        </div>
      </header>

      {exam.shortfall_note && (
        <p className="flex items-start gap-2 rounded-[var(--radius)] px-3 py-2 text-[11px] font-semibold"
           style={{ background: "var(--warning)", color: "var(--ink)",
                    border: "var(--line-width) solid var(--line)" }}>
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          Short paper: {exam.shortfall_note}. The bank could not fill every section.
        </p>
      )}

      <div className="grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
        <aside
          className="order-2 rounded-[var(--radius-lg)] p-4 lg:order-1 lg:sticky lg:top-4 lg:self-start"
          style={{ background: "var(--surface)",
                   border: "var(--line-width) solid var(--line)",
                   boxShadow: "var(--shadow-sm)" }}
        >
          <QuestionPalette
            questions={questions} current={current} onJump={goTo} counts={counts}
          />
        </aside>

        <section
          className="order-1 min-w-0 rounded-[var(--radius-lg)] p-4 lg:order-2"
          style={{ background: "var(--surface)",
                   border: "var(--line-width) solid var(--line)",
                   boxShadow: "var(--shadow-sm)" }}
        >
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-extrabold" style={{ color: "var(--ink)" }}>
              Question {question.position}
            </h2>
            <span className="flex items-center gap-2 text-[11px] font-bold"
                  style={{ color: "var(--ink-faint)" }}>
              <span>{question.subject_name}</span>
              <span
                className="rounded-[var(--radius-pill)] px-2 py-0.5"
                style={{ background: "var(--surface-sunk)",
                         border: "var(--line-width) solid var(--line)" }}
              >
                {question.question_type} · +{question.marks}
                {question.question_type === "MCQ" && ` / −${question.negative_marks}`}
              </span>
            </span>
          </div>

          <div className="mb-4 overflow-x-auto text-sm leading-relaxed"
               style={{ color: "var(--ink-soft)" }}>
            <MathText text={question.content} />
          </div>

          {question.question_type === "MSQ" && (
            <p className="mb-3 text-[11px] font-semibold" style={{ color: "var(--ink-faint)" }}>
              One or more options may be correct. No partial credit, no negative marking.
            </p>
          )}

          <AnswerInput question={question} value={draft} onChange={setDraft} />

          <div className="mt-5 flex flex-wrap gap-2 border-t pt-4"
               style={{ borderColor: "var(--line)" }}>
            <button
              type="button"
              onClick={() => { void persist(draft); goTo(current + 1); }}
              className="min-h-11 flex-1 rounded-[var(--radius-pill)] px-4 text-xs font-bold sm:flex-none"
              style={{ background: "var(--success)", color: "var(--ink)",
                       border: "var(--line-width) solid var(--line)",
                       boxShadow: "var(--shadow-sm)" }}
            >
              Save &amp; next
            </button>

            <button
              type="button"
              onClick={() => { void persist(draft, true); goTo(current + 1); }}
              className="flex min-h-11 items-center gap-1.5 rounded-[var(--radius-pill)] px-4 text-xs font-bold"
              style={{ background: "var(--accent)", color: "var(--ink)",
                       border: "var(--line-width) solid var(--line)" }}
            >
              <Flag className="h-3.5 w-3.5" />
              Mark &amp; next
            </button>

            <button
              type="button"
              onClick={() => { setDraft(""); void persist("", false); }}
              className="min-h-11 rounded-[var(--radius-pill)] px-4 text-xs font-bold"
              style={{ background: "var(--surface)", color: "var(--ink)",
                       border: "var(--line-width) solid var(--line)" }}
            >
              Clear response
            </button>

            <button
              type="button"
              onClick={() => goTo(current + 1)}
              className="min-h-11 rounded-[var(--radius-pill)] px-4 text-xs font-bold"
              style={{ background: "var(--surface-sunk)", color: "var(--ink-soft)",
                       border: "var(--line-width) solid var(--line)" }}
            >
              Skip
            </button>
          </div>
        </section>
      </div>
    </div>
  );
}
