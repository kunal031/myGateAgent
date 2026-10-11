"use client";

import SessionRunner from "./SessionRunner";

/**
 * A quiz: navigate freely, submit once, review afterwards.
 *
 * Identical to a test apart from wording and where the result lives, so the
 * behaviour lives in SessionRunner rather than in two copies that drift.
 */
export default function QuizRunner({ quizId }: { quizId: number }) {
  return <SessionRunner sessionId={quizId} kind="quiz" />;
}
