"use client";

import React, { useEffect, useState } from "react";
import { Loader2, X } from "lucide-react";

import { Panel, Row } from "@/components/Panel";
import { AdminUserDetail, AdminUserRow, fetchAdminUserDetail } from "@/lib/admin";

/**
 * One account's analytics, shown when an admin clicks a row.
 *
 * Every number here comes from services/analytics/performance -- the
 * same functions behind the student's own analytics page -- so what an
 * admin reads is by construction what that student reads.
 *
 * A dialog rather than a route: the admin's task is comparing accounts,
 * and a full page navigation loses the list position and the sort on
 * every back button.
 */

function fullDate(iso: string | null): string {
  if (!iso) return "never";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "never";
  return d.toLocaleString(undefined, {
    day: "numeric", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

/** A labelled proportion with a bar. Coverage is the headline number on
 *  the student's own page, so it leads here too. */
function Meter({ label, done, total, pct }: {
  label: string; done: number; total: number; pct: number;
}) {
  return (
    <div className="py-1.5">
      <div className="mb-1 flex items-baseline justify-between gap-2">
        <span className="text-[12px]" style={{ color: "var(--ink-soft)" }}>{label}</span>
        <span className="text-[12px] font-bold" style={{ color: "var(--ink)" }}>
          {done}
          <span style={{ color: "var(--ink-faint)" }}> / {total}</span>
        </span>
      </div>
      <div
        className="h-1.5 w-full overflow-hidden rounded-[var(--radius-pill)]"
        style={{ background: "var(--surface-sunk)" }}
      >
        <div
          className="h-full rounded-[var(--radius-pill)]"
          style={{
            width: `${Math.min(100, Math.max(0, pct))}%`,
            background: "var(--accent)",
          }}
        />
      </div>
    </div>
  );
}

/** Thirty days of attempts as bars. Consistency predicts the outcome
 *  better than any single session, so the shape matters more than the
 *  individual counts. */
function ActivityStrip({ days }: { days: AdminUserDetail["daily_activity"] }) {
  if (days.length === 0) {
    return (
      <p className="py-2 text-[12px]" style={{ color: "var(--ink-faint)" }}>
        No questions answered in the last 30 days.
      </p>
    );
  }
  const peak = Math.max(...days.map((d) => d.attempts), 1);
  return (
    <div className="flex items-end gap-0.5" style={{ height: 48 }}>
      {days.map((d) => (
        <div
          key={d.date}
          title={`${d.date}: ${d.attempts} answered, ${d.correct} correct`}
          className="min-w-0 flex-1 rounded-t-[2px]"
          style={{
            height: `${Math.max(6, (d.attempts / peak) * 100)}%`,
            background: "var(--accent)",
          }}
        />
      ))}
    </div>
  );
}

export default function UserDetail({
  user,
  onClose,
}: {
  user: AdminUserRow;
  onClose: () => void;
}) {
  const [detail, setDetail] = useState<AdminUserDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  // No reset of detail/error here: the parent keys this component by
  // user id, so picking a different row remounts it with fresh state.
  // Clearing them synchronously in the effect instead would cascade a
  // render on every open.
  useEffect(() => {
    let live = true;
    fetchAdminUserDetail(user.id)
      .then((d) => { if (live) setDetail(d); })
      .catch((e) => {
        if (live) setError(e instanceof Error ? e.message : "Could not load this account");
      });
    return () => { live = false; };
  }, [user.id]);

  // Escape closes, as in any dialog.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto p-3 sm:p-6">
      <button
        type="button"
        aria-label="Close"
        onClick={onClose}
        className="fixed inset-0 bg-black/50"
      />

      <div
        role="dialog"
        aria-modal="true"
        aria-label={`Analytics for ${user.email}`}
        className="relative z-10 w-full max-w-3xl space-y-3 rounded-[var(--radius-lg)] p-4"
        style={{
          background: "var(--surface-sunk)",
          border: "var(--line-width) solid var(--line)",
          boxShadow: "var(--shadow-lg, var(--shadow-sm))",
        }}
      >
        <header className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="truncate text-base font-extrabold" style={{ color: "var(--ink)" }}>
              {user.display_name || user.email.split("@")[0]}
            </h2>
            <p className="truncate text-[11px]" style={{ color: "var(--ink-faint)" }}>
              {user.email}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[var(--radius-pill)]"
            style={{
              border: "var(--line-width) solid var(--line)",
              color: "var(--ink)",
              background: "var(--surface)",
            }}
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        {error && (
          <p
            className="rounded-[var(--radius)] p-3 text-[12px]"
            style={{ background: "var(--surface)", color: "var(--danger, var(--ink))" }}
          >
            {error}
          </p>
        )}

        {!detail && !error && (
          <div className="flex justify-center py-10">
            <Loader2 className="h-5 w-5 animate-spin" style={{ color: "var(--ink-faint)" }} />
          </div>
        )}

        {detail && (
          <div className="grid gap-3 lg:grid-cols-2">
            <Panel title="Account">
              <Row label="Role" value={detail.user.role} />
              <Row label="Status" value={detail.user.is_active ? "Active" : "Disabled"} />
              <Row
                label="Sign-in"
                value={
                  [
                    detail.user.has_password ? "Password" : null,
                    detail.user.google_linked ? "Google" : null,
                  ].filter(Boolean).join(" + ") || "none"
                }
              />
              <Row label="Joined" value={fullDate(detail.user.created_at)} />
              <Row label="Last seen" value={fullDate(detail.user.last_login_at)} />
              <Row label="Cards written" value={user.cards_written} />
            </Panel>

            <Panel title="Readiness">
              <Row
                label="Projected marks"
                value={detail.readiness.projected_marks}
                hintOn="value"
                hint="/ 100"
              />
              <Row
                label="Confidence"
                value={detail.readiness.confidence}
                hint="basis, not a prediction"
              />
              <Row label="Assessed weight" value={`${detail.readiness.assessed_weight} marks`} />
              <Row label="Untested weight" value={`${detail.readiness.unassessed_weight} marks`} />
            </Panel>

            <Panel title="Coverage" span>
              <div className="grid gap-x-6 sm:grid-cols-2">
                <Meter
                  label="Questions seen"
                  done={detail.coverage.questions_seen}
                  total={detail.coverage.questions_total}
                  pct={detail.coverage.questions_pct}
                />
                <Meter
                  label="Concepts started"
                  done={detail.coverage.concepts_started}
                  total={detail.coverage.concepts_total}
                  pct={detail.coverage.concepts_pct}
                />
                <Meter
                  label="Subjects touched"
                  done={detail.coverage.subjects_touched}
                  total={detail.coverage.subjects_total}
                  pct={
                    detail.coverage.subjects_total
                      ? (detail.coverage.subjects_touched / detail.coverage.subjects_total) * 100
                      : 0
                  }
                />
                <Meter
                  label="Marks touched"
                  done={detail.coverage.marks_touched}
                  total={detail.coverage.marks_total}
                  pct={detail.coverage.marks_pct}
                />
              </div>
            </Panel>

            <Panel title="By question type">
              {detail.by_question_type.length === 0 ? (
                <p className="py-2 text-[12px]" style={{ color: "var(--ink-faint)" }}>
                  Nothing answered yet.
                </p>
              ) : (
                detail.by_question_type.map((q) => (
                  <Row
                    key={q.question_type}
                    label={q.question_type}
                    hint={`${q.attempts} tried, ${q.avg_seconds}s avg`}
                    value={q.accuracy === null ? "--" : `${q.accuracy}%`}
                  />
                ))
              )}
            </Panel>

            <Panel title="Retention">
              <Row label="Due now" value={detail.retention.due_now} />
              <Row label="Cards recalled" value={detail.retention.cards_recalled} />
              <Row label="Cards mastered" value={detail.retention.cards_mastered} />
              <Row
                label="Lapse rate"
                value={`${detail.retention.lapse_rate}%`}
                hintOn="value"
                hint={`${detail.retention.total_lapses} lapses`}
              />
            </Panel>

            <Panel title="Weakest topics" span>
              {detail.weak_topics.length === 0 ? (
                <p className="py-2 text-[12px]" style={{ color: "var(--ink-faint)" }}>
                  Not enough attempts to rank topics yet.
                </p>
              ) : (
                detail.weak_topics.map((t) => (
                  <Row
                    key={t.topic_id}
                    label={t.topic_name}
                    hint={`${t.subject_name} · ${t.attempts} tried`}
                    value={
                      <>
                        {t.accuracy}%
                        <span className="ml-1.5 font-normal" style={{ color: "var(--ink-faint)" }}>
                          {t.marks_at_stake} at stake
                        </span>
                      </>
                    }
                  />
                ))
              )}
            </Panel>

            <Panel title="Last 30 days" span>
              <ActivityStrip days={detail.daily_activity} />
            </Panel>
          </div>
        )}
      </div>
    </div>
  );
}
