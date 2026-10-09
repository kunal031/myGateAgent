"use client";

import React from "react";

import type { ExamQuestion, ExamState } from "@/lib/api";
import { PALETTE_ORDER, STATE_STYLE } from "./palette";

interface Props {
  questions: ExamQuestion[];
  current: number;
  onJump: (position: number) => void;
  counts: Record<ExamState, number>;
}

/** The grid of question numbers, colour-coded by state, as in the real exam. */
export default function QuestionPalette({ questions, current, onJump, counts }: Props) {
  return (
    <div className="space-y-4">
      <div
        className="grid grid-cols-5 gap-2"
        role="group"
        aria-label="Question palette"
      >
        {questions.map((q) => {
          const style = STATE_STYLE[q.state];
          const active = q.position === current;
          return (
            <button
              key={q.position}
              type="button"
              onClick={() => onJump(q.position)}
              aria-current={active ? "true" : undefined}
              aria-label={`Question ${q.position}, ${style.label}`}
              className="flex h-10 w-full items-center justify-center rounded-[var(--radius)] text-xs font-bold transition-transform"
              style={{
                background: style.background,
                color: style.color,
                border: `${active ? "3px" : "var(--line-width)"} solid ${
                  active ? "var(--ink)" : style.border
                }`,
                boxShadow: active ? "var(--shadow-sm)" : "none",
              }}
            >
              {q.position}
            </button>
          );
        })}
      </div>

      <dl className="space-y-1.5">
        {PALETTE_ORDER.map((state) => (
          <div key={state} className="flex items-center justify-between gap-2">
            <dt className="flex items-center gap-2 text-[11px] font-semibold"
                style={{ color: "var(--ink-soft)" }}>
              <span
                className="h-3.5 w-3.5 rounded-[4px]"
                style={{
                  background: STATE_STYLE[state].background,
                  border: "var(--line-width) solid var(--line)",
                }}
              />
              {STATE_STYLE[state].label}
            </dt>
            <dd className="text-[11px] font-bold" style={{ color: "var(--ink)" }}>
              {counts[state] ?? 0}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
