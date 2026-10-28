"use client";

import React, { useCallback, useState } from "react";
import {
  ArrowRight, Check, Loader2, MessageCircleQuestion, Sparkles, X,
} from "lucide-react";

import {
  QuizQuestion, SubmitResponse, generateSolution, submitQuizAnswer,
} from "@/lib/api";

import AnswerInput from "./AnswerInput";

/**
 * Practice: answer one question, see immediately whether it was right.
 *
 * The other flow is a quiz -- navigate freely, submit once, review at the
 * end -- which trains recall under exam conditions. This one trades that
 * for feedback while the reasoning is still fresh, which is what you
 * want when learning a topic rather than testing it.
 *
 * The solution stays hidden behind Explain even after answering. Showing
 * it automatically turns practice into reading: the eye goes to the
 * worked answer before the student has decided whether they understood
 * their own mistake.
 */
export default function PracticeRunner({
  questions, onExit,
}: {
  questions: QuizQuestion[];
  onExit: () => void;
}) {
  const [index, setIndex] = useState(0);
  const [answer, setAnswer] = useState("");
  const [result, setResult] = useState<SubmitResponse | null>(null);
  const [busy, setBusy] = useState(false);

  const [showSolution, setShowSolution] = useState(false);
  const [solution, setSolution] = useState<string>("");
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState("");

  const [score, setScore] = useState({ right: 0, wrong: 0 });
  const [startedAt, setStartedAt] = useState(() => Date.now());

  const question = questions[index];
  const last = index >= questions.length - 1;

  const check = useCallback(async () => {
    if (!answer.trim() || busy || result) return;
    setBusy(true);
    try {
      const response = await submitQuizAnswer({
        question_id: question.id,
        user_answer: answer.trim(),
        time_spent_seconds: Math.round((Date.now() - startedAt) / 1000),
        mode: "practice",
      });
      setResult(response);
      setSolution(response.explanation || "");
      setScore((s) => response.is_correct
        ? { ...s, right: s.right + 1 }
        : { ...s, wrong: s.wrong + 1 });
    } catch {
      // Left answerable rather than showing a banner: the student can
      // press again, and a failed submit has recorded nothing.
    } finally {
      setBusy(false);
    }
  }, [answer, busy, result, question, startedAt]);

  const next = useCallback(() => {
    if (last) { onExit(); return; }
    setIndex((i) => i + 1);
    setAnswer("");
    setResult(null);
    setShowSolution(false);
    setSolution("");
    setGenError("");
    setStartedAt(Date.now());
  }, [last, onExit]);

  const generate = useCallback(async () => {
    setGenerating(true);
    setGenError("");
    try {
      const { explanation } = await generateSolution(question.id);
      setSolution(explanation);
    } catch (err) {
      setGenError(err instanceof Error ? err.message : "Could not generate");
    } finally {
      setGenerating(false);
    }
  }, [question]);

  if (!question) {
    return (
      <p className="py-10 text-center text-[13px]" style={{ color: "var(--ink-faint)" }}>
        No questions matched those filters.
      </p>
    );
  }

  const correct = result?.is_correct === true;

  return (
    <div className="mx-auto w-full max-w-3xl space-y-3">
      <header className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          {/* The full path, so a question's place in the syllabus is
              visible while answering it -- and a misfiled one is
              obvious rather than silently miscounted. */}
          <p className="truncate text-[11px]" style={{ color: "var(--ink-faint)" }}>
            {question.subject_name}
            {question.chapter_name && ` › ${question.chapter_name}`}
            {` › ${question.topic_name}`}
          </p>
          <p className="text-[11px] font-semibold" style={{ color: "var(--ink-soft)" }}>
            Question {index + 1} of {questions.length}
            {question.is_pyq && (
              <span style={{ color: "var(--ink-faint)" }}>
                {question.exam_year
                  ? ` · GATE ${question.exam_year}${
                      question.exam_set ? ` ${question.exam_set}` : ""
                    }`
                  : " · previous year"}
              </span>
            )}
          </p>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <span className="font-mono text-[12px] font-bold"
                style={{ color: "var(--ok, #10b981)" }}>{score.right}</span>
          <span className="font-mono text-[12px] font-bold"
                style={{ color: "var(--bad, #f43f5e)" }}>{score.wrong}</span>
          <button type="button" onClick={onExit} aria-label="Leave practice"
                  className="flex h-8 w-8 items-center justify-center rounded-[var(--radius)]"
                  style={{ border: "var(--line-width) solid var(--line)",
                           color: "var(--ink)" }}>
            <X className="h-4 w-4" />
          </button>
        </div>
      </header>

      <section className="rounded-[var(--radius-lg)] p-4"
               style={{ background: "var(--surface)",
                        border: "var(--line-width) solid var(--line)" }}>
        <p className="whitespace-pre-wrap text-[14px] leading-relaxed"
           style={{ color: "var(--ink)" }}>
          {question.content}
        </p>

        {/* Locked once checked by refusing changes and dimming the
            control, rather than adding a `disabled` prop to AnswerInput
            that the quiz and exam runners would also have to carry. */}
        <div className="mt-3" style={{ opacity: result ? 0.6 : 1 }}>
          <AnswerInput
            question={{
              position: index + 1,
              question_id: question.id,
              question_type: question.question_type,
              marks: question.marks,
              negative_marks: question.negative_marks,
              content: question.content,
              options: question.options,
              subject_name: question.subject_name,
              state: "answered",
              user_answer: answer,
              time_spent_seconds: 0,
            }}
            value={answer}
            onChange={(v) => { if (!result) setAnswer(v); }}
          />
        </div>

        {result && (
          <div className="mt-3 rounded-[var(--radius)] px-3 py-2.5"
               style={{
                 background: correct ? "var(--ok-bg, #10b98118)"
                                     : "var(--bad-bg, #f43f5e18)",
                 border: "var(--line-width) solid var(--line)",
               }}>
            <p className="flex items-center gap-1.5 text-[13px] font-bold"
               style={{ color: correct ? "var(--ok, #10b981)"
                                       : "var(--bad, #f43f5e)" }}>
              {correct ? <Check className="h-4 w-4" /> : <X className="h-4 w-4" />}
              {correct ? "Correct" : "Not quite"}
            </p>
            {!correct && (
              <p className="mt-1 text-[12px]" style={{ color: "var(--ink-soft)" }}>
                The answer is <strong>{result.correct_answer}</strong>
              </p>
            )}
            <p className="mt-0.5 text-[11px]" style={{ color: "var(--ink-faint)" }}>
              {result.marks_awarded > 0 ? "+" : ""}{result.marks_awarded} marks
            </p>
          </div>
        )}
      </section>

      {result && (
        <section className="space-y-2">
          {!showSolution ? (
            <button
              type="button"
              onClick={() => setShowSolution(true)}
              className="flex min-h-10 w-full items-center justify-center gap-1.5 rounded-[var(--radius-pill)] text-[12px] font-bold"
              style={{ background: "var(--surface)", color: "var(--ink)",
                       border: "var(--line-width) solid var(--line)" }}
            >
              <MessageCircleQuestion className="h-3.5 w-3.5" />
              Explain
            </button>
          ) : (
            <div className="rounded-[var(--radius-lg)] p-4"
                 style={{ background: "var(--surface)",
                          border: "var(--line-width) solid var(--line)" }}>
              {solution ? (
                <>
                  <p className="mb-1.5 text-[10px] font-extrabold uppercase tracking-wider"
                     style={{ color: "var(--ink-faint)" }}>
                    Solution
                    {result.explanation ? "" : " · generated"}
                  </p>
                  <p className="whitespace-pre-wrap text-[13px] leading-relaxed"
                     style={{ color: "var(--ink)" }}>
                    {solution}
                  </p>
                </>
              ) : (
                <>
                  {/* Said plainly, as asked: 1,200 of 1,953 questions have
                      no recorded solution, so this is the common case and
                      dressing it up would waste the student's time. */}
                  <p className="text-[13px]" style={{ color: "var(--ink-soft)" }}>
                    No solution is recorded for this question.
                  </p>
                  {genError && (
                    <p className="mt-1.5 text-[11px] font-semibold"
                       style={{ color: "var(--bad, #f43f5e)" }}>
                      {genError}
                    </p>
                  )}
                  <button
                    type="button"
                    onClick={generate}
                    disabled={generating}
                    className="mt-2.5 flex min-h-9 items-center justify-center gap-1.5 rounded-[var(--radius-pill)] px-3 text-[12px] font-bold disabled:opacity-50"
                    style={{ background: "var(--accent)", color: "var(--ink)",
                             border: "var(--line-width) solid var(--line)" }}
                  >
                    {generating
                      ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      : <Sparkles className="h-3.5 w-3.5" />}
                    {generating ? "Writing one…" : "Generate a solution"}
                  </button>
                </>
              )}
            </div>
          )}
        </section>
      )}

      <button
        type="button"
        onClick={result ? next : check}
        disabled={busy || (!result && !answer.trim())}
        className="flex min-h-11 w-full items-center justify-center gap-1.5 rounded-[var(--radius-pill)] text-[13px] font-bold disabled:opacity-40"
        style={{ background: "var(--accent)", color: "var(--ink)",
                 border: "var(--line-width) solid var(--line)" }}
      >
        {busy && <Loader2 className="h-4 w-4 animate-spin" />}
        {result ? (last ? "Finish" : "Next question") : "Check answer"}
        {result && !last && <ArrowRight className="h-4 w-4" />}
      </button>
    </div>
  );
}
