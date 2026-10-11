"use client";

import SessionRunner from "./SessionRunner";

/** A mock test under exam conditions. See SessionRunner for the behaviour. */
export default function ExamRunner({ examId }: { examId: number }) {
  return <SessionRunner sessionId={examId} kind="test" />;
}
