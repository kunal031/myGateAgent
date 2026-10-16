"use client";

import React from "react";

import MathText from "@/components/MathText";
import type { ExamQuestion } from "@/lib/api";

interface Props {
  question: ExamQuestion;
  value: string;
  onChange: (value: string) => void;
}

/** Answer control for the question's type: single, multiple, or numeric. */
export default function AnswerInput({ question, value, onChange }: Props) {
  if (question.question_type === "NAT") {
    return (
      <div
        className="flex flex-wrap items-center gap-3 rounded-[var(--radius)] px-4 py-3"
        style={{
          background: "var(--surface-sunk)",
          border: "var(--line-width) solid var(--line)",
        }}
      >
        <label htmlFor="nat-answer" className="text-xs font-bold"
               style={{ color: "var(--ink-soft)" }}>
          Your answer
        </label>
        <input
          id="nat-answer"
          type="number"
          step="any"
          inputMode="decimal"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Numeric value"
          className="min-h-11 w-48 rounded-[var(--radius)] px-3 font-mono text-sm"
          style={{
            background: "var(--surface)",
            border: "var(--line-width) solid var(--line)",
            color: "var(--ink)",
          }}
        />
      </div>
    );
  }

  const isMulti = question.question_type === "MSQ";
  const selected = value ? value.split(",").filter(Boolean) : [];

  const toggle = (id: string) => {
    if (!isMulti) {
      onChange(selected[0] === id ? "" : id);
      return;
    }
    const next = selected.includes(id)
      ? selected.filter((s) => s !== id)
      : [...selected, id].sort();
    onChange(next.join(","));
  };

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {question.options?.map((option) => {
        const active = selected.includes(option.id);
        return (
          <button
            key={option.id}
            type="button"
            onClick={() => toggle(option.id)}
            aria-pressed={active}
            className="flex min-h-14 items-center gap-3 rounded-[var(--radius)] px-3 py-2.5 text-left text-sm transition-colors"
            style={{
              background: active ? "var(--accent)" : "var(--surface)",
              border: `${active ? "3px" : "var(--line-width)"} solid var(--line)`,
              color: "var(--ink)",
              boxShadow: active ? "var(--shadow-sm)" : "none",
            }}
          >
            <span
              className="flex h-8 w-8 shrink-0 items-center justify-center text-xs font-extrabold"
              style={{
                background: active ? "var(--surface)" : "var(--surface-sunk)",
                border: "var(--line-width) solid var(--line)",
                borderRadius: isMulti ? "6px" : "999px",
              }}
            >
              {option.id}
            </span>
            <span className="min-w-0 flex-1">
              <MathText text={option.text} />
            </span>
          </button>
        );
      })}
    </div>
  );
}
