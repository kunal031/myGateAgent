"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, CheckCircle2, Clock, XCircle } from "lucide-react";

import MathText from "@/components/MathText";
import {
  CheckResponse, ExamQuestion, ExamSummary,
  checkQuizAnswer, fetchExam, saveExamAnswer, submitExam, visitExamQuestion,
} from "@/lib/api";
import AnswerInput from "./AnswerInput";
import { formatClock } from "./palette";

/**
 * A quiz: one question at a time, graded on submit with the explanation
 * shown straight away. That immediate feedback is the whole point -- a test
 * withholds it until the end, a quiz is for learning while it is fresh.
 */
export default function QuizRunner({ quizId }: { quizId: number }) {
  const router = useRouter();
  const [quiz, setQuiz] = useState<ExamSummary | null>(null);
  const [questions, setQuestions] = useState<ExamQuestion[]>([]);
  const [index, setIndex] = useState(0);
  const [draft, setDraft] = useState("");
  const [feedback, setFeedback] = useState<CheckResponse | null>(null);
  const [remaining, setRemaining] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const enteredAt = useRef<number | null>(null);
  const question = questions[index];

  useEffect(() => {
    let cancelled = false;
    fetchExam(quizId)
      .then((data) => {
        if (cancelled) return;
        setQuiz(data);
        setQuestions(data.questions ?? []);
        setRemaining(data.remaining_seconds);
        void visitExamQuestion(quizId, 1);
      })
      .catch(() => !cancelled && setError("Could not load this quiz."));
    return () => { cancelled = true; };
  }, [quizId]);

  const finish = useCallback(async () => {
    setBusy(true);
    try {
      await submitExam(quizId);
      router.push(`/quiz/${quizId}/result`);
    } catch {
      setError("Could not finish the quiz.");
      setBusy(false);
    }
  }, [quizId, router]);

  useEffect(() => {
    if (!quiz || quiz.status !== "in_progress") return;
    const timer = window.setInterval(() => {
      setRemaining((prev) => {
        if (prev <= 1) {
          window.clearInterval(timer);
          void finish();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => window.clearInterval(timer);
  }, [quiz, finish]);

  const check = async () => {
    if (!question || !draft) return;
    setBusy(true);
    try {
      const spent = enteredAt.current
        ? Math.round((Date.now() - enteredAt.current) / 1000)
        : 0;
      await saveExamAnswer(quizId, question.position, {
        answer: draft, time_spent_seconds: spent,
      });
      setFeedback(await checkQuizAnswer(quizId, question.position));
    } catch {
      setError("Could not check that answer.");
    } finally {
      setBusy(false);
    }
  };

  const next = () => {
    if (index + 1 >= questions.length) { void finish(); return; }
    const position = questions[index + 1].position;
    setIndex(index + 1);
    setDraft("");
    setFeedback(null);
    enteredAt.current = Date.now();
    void visitExamQuestion(quizId, position);
  };

  const skip = () => {
    if (feedback) { next(); return; }
    next();
  };

  if (error) {
    return <p className="rounded-[var(--radius)] px-4 py-3 text-sm font-semibold"
              style={{ background: "var(--danger)", color: "var(--ink)",
                       border: "var(--line-width) solid var(--line)" }}>{error}</p>;
  }
  if (!quiz || !question) {
    return <p className="py-16 text-center text-xs font-semibold"
              style={{ color: "var(--ink-faint)" }}>Loading quiz...</p>;
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-base font-extrabold" style={{ color: "var(--ink)" }}>
            {quiz.name}
          </h1>
          <p className="text-[11px] font-semibold" style={{ color: "var(--ink-faint)" }}>
            Question {index + 1} of {questions.length} · {question.subject_name}
          </p>
        </div>
        <span className="flex min-h-11 items-center gap-2 rounded-[var(--radius-pill)] px-4 font-mono text-sm font-bold"
              style={{ background: remaining < 60 ? "var(--danger)" : "var(--surface)",
                       border: "var(--line-width) solid var(--line)", color: "var(--ink)" }}>
          <Clock className="h-4 w-4" />
          {formatClock(remaining)}
        </span>
      </header>

      <div className="h-1.5 w-full overflow-hidden rounded-[var(--radius-pill)]"
           style={{ background: "var(--surface-sunk)",
                    border: "var(--line-width) solid var(--line)" }}>
        <div className="h-full transition-all"
             style={{ width: `${((index + 1) / questions.length) * 100}%`,
                      background: "var(--accent)" }} />
      </div>

      <section className="space-y-4 rounded-[var(--radius-lg)] p-4"
               style={{ background: "var(--surface)",
                        border: "var(--line-width) solid var(--line)",
                        boxShadow: "var(--shadow-sm)" }}>
        <div className="flex items-center justify-between gap-2">
          <span className="rounded-[var(--radius-pill)] px-2.5 py-1 text-[10px] font-extrabold"
                style={{ background: "var(--surface-sunk)",
                         border: "var(--line-width) solid var(--line)",
                         color: "var(--ink)" }}>
            {question.question_type} · +{question.marks}
            {question.question_type === "MCQ" && ` / −${question.negative_marks}`}
          </span>
        </div>

        <div className="overflow-x-auto text-sm leading-relaxed" style={{ color: "var(--ink-soft)" }}>
          <MathText text={question.content} />
        </div>

        <div style={{ pointerEvents: feedback ? "none" : "auto",
                      opacity: feedback ? 0.75 : 1 }}>
          <AnswerInput question={question} value={draft} onChange={setDraft} />
        </div>

        {feedback && (
          <div className="space-y-2 rounded-[var(--radius)] px-3 py-3"
               style={{ background: feedback.is_correct ? "var(--success)" : "var(--danger)",
                        border: "var(--line-width) solid var(--line)" }}>
            <p className="flex items-center gap-2 text-xs font-extrabold"
               style={{ color: "var(--ink)" }}>
              {feedback.is_correct
                ? <><CheckCircle2 className="h-4 w-4" /> Correct · +{feedback.marks_obtained}</>
                : <><XCircle className="h-4 w-4" /> Incorrect · {feedback.marks_obtained} · answer {feedback.correct_answer}</>}
            </p>
            <div className="overflow-x-auto rounded-[var(--radius)] px-3 py-2 text-[13px]"
                 style={{ background: "var(--surface)",
                          border: "var(--line-width) solid var(--line)",
                          color: "var(--ink)" }}>
              <MathText text={feedback.explanation} />
            </div>
          </div>
        )}

        <div className="flex flex-wrap gap-2 border-t pt-4" style={{ borderColor: "var(--line)" }}>
          {!feedback ? (
            <>
              <button type="button" onClick={check} disabled={busy || !draft}
                      className="min-h-11 flex-1 rounded-[var(--radius-pill)] px-4 text-xs font-bold disabled:opacity-50 sm:flex-none"
                      style={{ background: "var(--success)", color: "var(--ink)",
                               border: "var(--line-width) solid var(--line)",
                               boxShadow: "var(--shadow-sm)" }}>
                {busy ? "Checking..." : "Check answer"}
              </button>
              <button type="button" onClick={skip}
                      className="min-h-11 rounded-[var(--radius-pill)] px-4 text-xs font-bold"
                      style={{ background: "var(--surface-sunk)", color: "var(--ink-soft)",
                               border: "var(--line-width) solid var(--line)" }}>
                Skip
              </button>
            </>
          ) : (
            <button type="button" onClick={next} disabled={busy}
                    className="flex min-h-11 flex-1 items-center justify-center gap-1.5 rounded-[var(--radius-pill)] px-4 text-xs font-bold sm:flex-none"
                    style={{ background: "var(--accent)", color: "var(--ink)",
                             border: "var(--line-width) solid var(--line)",
                             boxShadow: "var(--shadow-sm)" }}>
              {index + 1 >= questions.length ? "Finish quiz" : "Next question"}
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          )}

          <button type="button" onClick={finish} disabled={busy}
                  className="min-h-11 rounded-[var(--radius-pill)] px-4 text-xs font-bold"
                  style={{ background: "var(--surface)", color: "var(--ink)",
                           border: "var(--line-width) solid var(--line)" }}>
            End quiz
          </button>
        </div>
      </section>
    </div>
  );
}
