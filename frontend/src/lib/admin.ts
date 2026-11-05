/**
 * Admin-only reads: who is using this instance, and how.
 *
 * Its own module rather than more of api.ts, which is already 800 lines
 * covering every feature. Nothing else imports these, so they do not
 * belong in the file every page pulls from.
 *
 * The shapes below are transcribed from services/analytics/performance,
 * not inferred from the field names the UI would like. Five of them
 * differ from the obvious guess -- `date` not `day`, `topic_name` not
 * `topic`, `questions_seen` not `questions_attempted` -- and TypeScript
 * cannot catch that mismatch because the response is parsed JSON.
 *
 * The role check that hides the nav link is cosmetic. The backend guard
 * is admin_user, which reads the role from the database on every
 * request, so a student calling these directly gets 403.
 */

import { api } from "./client/web";

/** One row of the user list. */
export interface AdminUserRow {
  id: number;
  email: string;
  display_name: string;
  role: "student" | "admin";
  is_active: boolean;
  avatar_url: string | null;
  has_password: boolean;
  google_linked: boolean;
  created_at: string | null;
  last_login_at: string | null;
  attempts: number;
  correct: number;
  /** null, not 0, for an account that has answered nothing: 0% reads as
   *  "got everything wrong". */
  accuracy: number | null;
  cards_written: number;
  attempts_last_7d: number;
}

export interface AdminUserList {
  items: AdminUserRow[];
  total: number;
}

export interface AdminCoverage {
  questions_seen: number;
  questions_total: number;
  questions_pct: number;
  concepts_started: number;
  concepts_total: number;
  concepts_pct: number;
  marks_touched: number;
  marks_total: number;
  marks_pct: number;
  subjects_touched: number;
  subjects_total: number;
}

export interface AdminReadiness {
  projected_marks: number;
  assessed_weight: number;
  unassessed_weight: number;
  /** low | moderate | good -- the projection's own basis, not a score. */
  confidence: string;
  untested_subjects: { name?: string; weightage_marks: number }[];
}

export interface AdminQuestionType {
  question_type: string;
  attempts: number;
  correct: number;
  accuracy: number | null;
  avg_seconds: number;
  marks: number;
}

export interface AdminWeakTopic {
  topic_id: number;
  topic_name: string;
  topic_slug: string;
  subject_name: string;
  subject_slug: string;
  attempts: number;
  accuracy: number;
  marks_at_stake: number;
}

export interface AdminRetention {
  cards_seen: number;
  cards_recalled: number;
  cards_mastered: number;
  total_lapses: number;
  lapse_rate: number;
  due_now: number;
  concepts_by_status: Record<string, number>;
}

export interface AdminDailyActivity {
  date: string;
  attempts: number;
  correct: number;
}

export interface AdminUserDetail {
  user: {
    id: number;
    email: string;
    display_name: string;
    role: "student" | "admin";
    is_active: boolean;
    avatar_url: string | null;
    has_password: boolean;
    google_linked: boolean;
    created_at: string | null;
    last_login_at: string | null;
  };
  coverage: AdminCoverage;
  readiness: AdminReadiness;
  by_question_type: AdminQuestionType[];
  weak_topics: AdminWeakTopic[];
  retention: AdminRetention;
  daily_activity: AdminDailyActivity[];
}

export async function fetchAdminUsers(): Promise<AdminUserList> {
  return api.get(`/api/admin/users`);
}

export async function fetchAdminUserDetail(
  userId: number,
): Promise<AdminUserDetail> {
  return api.get(`/api/admin/users/${userId}`);
}
