import type { ExamState } from "@/lib/api";

/** Colour and label for each official GATE palette state. */
export const STATE_STYLE: Record<
  ExamState,
  { label: string; background: string; color: string; border: string }
> = {
  not_visited: {
    label: "Not visited",
    background: "var(--surface)",
    color: "var(--ink-faint)",
    border: "var(--line)",
  },
  not_answered: {
    label: "Not answered",
    background: "var(--danger)",
    color: "var(--ink)",
    border: "var(--line)",
  },
  answered: {
    label: "Answered",
    background: "var(--success)",
    color: "var(--ink)",
    border: "var(--line)",
  },
  marked: {
    label: "Marked for review",
    background: "var(--accent)",
    color: "var(--ink)",
    border: "var(--line)",
  },
  answered_marked: {
    label: "Answered & marked",
    background: "var(--info)",
    color: "var(--ink)",
    border: "var(--line)",
  },
};

export const PALETTE_ORDER: ExamState[] = [
  "answered",
  "not_answered",
  "marked",
  "answered_marked",
  "not_visited",
];

export function formatClock(totalSeconds: number): string {
  const seconds = Math.max(0, Math.floor(totalSeconds));
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${pad(h)}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
}
