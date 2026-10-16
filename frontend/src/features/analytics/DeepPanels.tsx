"use client";

import React, { useEffect, useState } from "react";
import { Flame, Target, TrendingDown, TrendingUp } from "lucide-react";

import { DeepAnalytics, fetchDeepAnalytics } from "@/lib/api";

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section
      className="rounded-[var(--radius)] p-3"
      style={{
        background: "var(--surface)",
        border: "var(--line-width) solid var(--line)",
      }}
    >
      <h3 className="mb-2 text-[11px] font-extrabold uppercase tracking-wider"
          style={{ color: "var(--ink-faint)" }}>
        {title}
      </h3>
      {children}
    </section>
  );
}

function Row({ label, value, hint }: {
  label: string; value: string | number; hint?: string;
}) {
  return (
    <div className="flex items-baseline justify-between gap-2 py-1">
      <span className="min-w-0 truncate text-[12px]" style={{ color: "var(--ink-soft)" }}>
        {label}
      </span>
      <span className="shrink-0 text-[13px] font-bold" style={{ color: "var(--ink)" }}>
        {value}
        {hint && (
          <span className="ml-1 text-[10px] font-semibold"
                style={{ color: "var(--ink-faint)" }}>
            {hint}
          </span>
        )}
      </span>
    </div>
  );
}

/** The analyses behind the insights, for when the summary is not enough. */
export default function DeepPanels() {
  const [data, setData] = useState<DeepAnalytics | null>(null);

  useEffect(() => {
    fetchDeepAnalytics().then(setData).catch(() => {});
  }, []);

  if (!data) return null;

  const { readiness, pace, trend, by_question_type, weak_topics,
          retention, exam_behaviour, distractors } = data;

  const TrendIcon = trend.direction === "improving" ? TrendingUp
    : trend.direction === "declining" ? TrendingDown : Target;

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <Card title="Projected score">
        <p className="text-2xl font-extrabold" style={{ color: "var(--ink)" }}>
          {readiness.projected_marks}
          <span className="ml-1 text-[12px] font-semibold"
                style={{ color: "var(--ink-faint)" }}>
            / 100 marks
          </span>
        </p>
        <p className="mt-1 text-[11px]" style={{ color: "var(--ink-faint)" }}>
          {/* Said plainly, because a projection from a quarter of the
              syllabus is not a score prediction. */}
          Based on {readiness.assessed_weight} marks of syllabus tested
          {readiness.unassessed_weight > 0
            && ` · ${readiness.unassessed_weight} still untested`}
          {" · "}confidence {readiness.confidence}
        </p>
      </Card>

      <Card title="Direction">
        <div className="flex items-center gap-2">
          <TrendIcon className="h-5 w-5" style={{ color: "var(--ink)" }} />
          <p className="text-2xl font-extrabold" style={{ color: "var(--ink)" }}>
            {trend.recent_accuracy ?? "–"}
            {trend.recent_accuracy !== null && "%"}
          </p>
        </div>
        <p className="mt-1 text-[11px]" style={{ color: "var(--ink-faint)" }}>
          last {trend.window_days} days
          {trend.change !== null
            && ` · ${trend.change > 0 ? "+" : ""}${trend.change} points vs before`}
        </p>
      </Card>

      {pace.samples > 0 && (
        <Card title="Pace">
          <Row label="Time on questions"
               value={`${pace.total_minutes ?? 0} min`} />
          <Row label="Over time budget"
               value={`${pace.over_budget ?? 0}`}
               hint={`${pace.over_budget_pct ?? 0}%`} />
          <Row label="Slow and still wrong" value={pace.slow_and_wrong ?? 0} />
          <Row label="Rushed errors" value={pace.rushed_errors ?? 0} />
        </Card>
      )}

      {by_question_type.length > 0 && (
        <Card title="By question type">
          {by_question_type.map((row) => (
            <Row
              key={row.question_type}
              label={`${row.question_type} · ${row.attempts} attempted`}
              value={`${row.accuracy}%`}
              hint={`${row.avg_seconds}s avg`}
            />
          ))}
        </Card>
      )}

      {weak_topics.length > 0 && (
        <Card title="Worth the most marks">
          {weak_topics.slice(0, 5).map((row) => (
            <Row
              key={row.topic_slug}
              label={row.topic_name}
              value={`${row.marks_at_stake}M`}
              hint={`${row.accuracy}%`}
            />
          ))}
        </Card>
      )}

      {retention.cards_seen > 0 && (
        <Card title="Retention">
          <Row label="Cards recalled" value={retention.cards_recalled} />
          <Row label="Mastered" value={retention.cards_mastered} />
          <Row label="Lapse rate" value={`${retention.lapse_rate}%`} />
          <Row label="Due now" value={retention.due_now} />
        </Card>
      )}

      {exam_behaviour.sessions > 0 && (
        <Card title="In timed papers">
          <Row label="Papers submitted" value={exam_behaviour.sessions} />
          <Row label="Left unanswered"
               value={exam_behaviour.unattempted ?? 0}
               hint={`${exam_behaviour.unattempted_pct ?? 0}%`} />
          <Row label="Best score" value={exam_behaviour.best_score ?? 0} />
          <Row label="Average accuracy"
               value={`${exam_behaviour.avg_accuracy ?? 0}%`} />
        </Card>
      )}

      {distractors.length > 0 && (
        <Card title="Repeated mistakes">
          {distractors.slice(0, 4).map((row) => (
            <div key={row.question_id} className="py-1.5">
              <p className="truncate text-[12px]" style={{ color: "var(--ink-soft)" }}>
                {row.question}
              </p>
              <p className="text-[11px] font-semibold"
                 style={{ color: "var(--ink-faint)" }}>
                <Flame className="mr-1 inline h-3 w-3" />
                {row.times_wrong}× wrong · you chose {row.your_answer},
                answer is {row.correct_answer}
              </p>
            </div>
          ))}
        </Card>
      )}
    </div>
  );
}
