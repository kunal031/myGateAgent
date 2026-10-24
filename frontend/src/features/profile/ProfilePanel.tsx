"use client";

import React, { useEffect, useState } from "react";
import {
  BookOpen, Brain, CheckCircle2, Clock, Flame, KeyRound, Loader2,
  Target, X,
} from "lucide-react";

import {
  ProfileInfo, ProfileStats, changePassword, fetchProfile,
  fetchProfileStats, updateProfile,
} from "@/lib/api";
import { storeSession } from "@/lib/auth";

type Tab = "info" | "manage";

function Stat({ icon: Icon, label, value, hint }: {
  icon: typeof Target; label: string; value: string | number; hint?: string;
}) {
  return (
    <div className="rounded-[var(--radius)] px-3 py-2.5"
         style={{ background: "var(--surface-sunk)",
                  border: "var(--line-width) solid var(--line)" }}>
      <div className="flex items-center gap-1.5">
        <Icon className="h-3.5 w-3.5" style={{ color: "var(--ink-faint)" }} />
        <span className="text-[10px] font-extrabold uppercase tracking-wider"
              style={{ color: "var(--ink-faint)" }}>
          {label}
        </span>
      </div>
      <p className="mt-1 text-xl font-extrabold leading-none"
         style={{ color: "var(--ink)" }}>
        {value}
      </p>
      {hint && (
        <p className="mt-0.5 text-[10px]" style={{ color: "var(--ink-faint)" }}>
          {hint}
        </p>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1.5">
      <span className="text-[12px]" style={{ color: "var(--ink-soft)" }}>{label}</span>
      <span className="text-right text-[12px] font-bold" style={{ color: "var(--ink)" }}>
        {value}
      </span>
    </div>
  );
}

/** The profile overlay: your details and numbers, or the form to change them. */
export default function ProfilePanel({ tab, onClose }: {
  tab: Tab; onClose: () => void;
}) {
  const [active, setActive] = useState<Tab>(tab);
  const [profile, setProfile] = useState<ProfileInfo | null>(null);
  const [stats, setStats] = useState<ProfileStats | null>(null);

  useEffect(() => {
    fetchProfile().then(setProfile).catch(() => {});
    fetchProfileStats().then(setStats).catch(() => {});
  }, []);

  // Escape closes, and background scroll is locked while the sheet covers
  // the screen -- on mobile the page otherwise scrolls under the overlay.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-[60] flex items-end justify-center sm:items-center"
         style={{ background: "color-mix(in oklab, var(--canvas) 70%, transparent)" }}
         onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        className="max-h-[92dvh] w-full overflow-y-auto rounded-t-[var(--radius-lg)] p-4 sm:max-w-lg sm:rounded-[var(--radius-lg)]"
        style={{ background: "var(--surface)",
                 border: "var(--line-width) solid var(--line)",
                 boxShadow: "var(--shadow)" }}
      >
        <div className="mb-3 flex items-center justify-between gap-2">
          <div className="flex gap-1 rounded-[var(--radius-pill)] p-0.5"
               style={{ background: "var(--surface-sunk)",
                        border: "var(--line-width) solid var(--line)" }}>
            {(["info", "manage"] as Tab[]).map((t) => (
              <button
                key={t} type="button" onClick={() => setActive(t)}
                className="rounded-[var(--radius-pill)] px-3 py-1.5 text-[11px] font-extrabold uppercase tracking-wider"
                style={active === t
                  ? { background: "var(--accent)", color: "var(--ink)" }
                  : { background: "transparent", color: "var(--ink-faint)" }}
              >
                {t === "info" ? "Info" : "Manage"}
              </button>
            ))}
          </div>
          <button type="button" onClick={onClose} aria-label="Close"
                  className="flex h-9 w-9 items-center justify-center rounded-[var(--radius)]"
                  style={{ border: "var(--line-width) solid var(--line)",
                           color: "var(--ink)" }}>
            <X className="h-4 w-4" />
          </button>
        </div>

        {active === "info"
          ? <InfoTab profile={profile} stats={stats} />
          : <ManageTab profile={profile} onSaved={setProfile} />}
      </div>
    </div>
  );
}

function InfoTab({ profile, stats }: {
  profile: ProfileInfo | null; stats: ProfileStats | null;
}) {
  if (!profile) {
    return (
      <div className="flex justify-center py-8">
        <Loader2 className="h-5 w-5 animate-spin" style={{ color: "var(--ink-faint)" }} />
      </div>
    );
  }

  const q = stats?.questions;
  const quizzes = stats?.tests.find((t) => t.kind === "quiz");
  const tests = stats?.tests.find((t) => t.kind === "test");

  return (
    <div className="space-y-4">
      <section>
        <h3 className="mb-1 text-[10px] font-extrabold uppercase tracking-wider"
            style={{ color: "var(--ink-faint)" }}>Account</h3>
        <div style={{ borderTop: "var(--line-width) solid var(--line)" }}>
          <Row label="Name" value={profile.display_name || "—"} />
          <Row label="Email" value={profile.email} />
          <Row label="Phone" value={profile.phone || "—"} />
          <Row label="Role" value={profile.role} />
          <Row label="Sign-in"
               value={[profile.has_password && "password",
                       profile.google_linked && "Google"]
                 .filter(Boolean).join(" + ") || "—"} />
          {profile.created_at && (
            <Row label="Joined"
                 value={new Date(profile.created_at).toLocaleDateString()} />
          )}
        </div>
      </section>

      {stats && (
        <>
          <section>
            <h3 className="mb-2 text-[10px] font-extrabold uppercase tracking-wider"
                style={{ color: "var(--ink-faint)" }}>Progress</h3>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <Stat icon={Brain} label="Concepts" value={stats.concepts.learned}
                    hint={`${stats.concepts.touched} started`} />
              <Stat icon={CheckCircle2} label="Solved" value={q?.distinct ?? 0}
                    hint={`${q?.attempted ?? 0} attempts`} />
              <Stat icon={Target} label="Accuracy"
                    value={q?.accuracy === null || q?.accuracy === undefined
                      ? "—" : `${q.accuracy}%`}
                    hint={`${q?.correct ?? 0} right`} />
              <Stat icon={Flame} label="Active days" value={stats.active_days} />
            </div>
          </section>

          <section>
            <h3 className="mb-1 text-[10px] font-extrabold uppercase tracking-wider"
                style={{ color: "var(--ink-faint)" }}>Questions</h3>
            <div style={{ borderTop: "var(--line-width) solid var(--line)" }}>
              <Row label="Right / wrong"
                   value={`${q?.correct ?? 0} / ${q?.wrong ?? 0}`} />
              <Row label="Marks earned" value={q?.marks_earned ?? 0} />
              <Row label="Time on questions"
                   value={`${q?.minutes_spent ?? 0} min`} />
              <Row label="Open mistakes" value={stats.open_mistakes} />
              {q?.by_type.map((b) => (
                <Row key={b.question_type}
                     label={`${b.question_type} · ${b.attempts} attempted`}
                     value={b.accuracy === null ? "—" : `${b.accuracy}%`} />
              ))}
            </div>
          </section>

          <section>
            <h3 className="mb-1 text-[10px] font-extrabold uppercase tracking-wider"
                style={{ color: "var(--ink-faint)" }}>Quizzes & tests</h3>
            <div style={{ borderTop: "var(--line-width) solid var(--line)" }}>
              <Row label="Quizzes submitted" value={quizzes?.submitted ?? 0} />
              {quizzes && (
                <>
                  <Row label="Best quiz score" value={quizzes.best_score} />
                  <Row label="Average accuracy" value={`${quizzes.avg_accuracy}%`} />
                </>
              )}
              <Row label="Tests submitted" value={tests?.submitted ?? 0} />
              {tests && <Row label="Best test score" value={tests.best_score} />}
            </div>
          </section>

          <section>
            <h3 className="mb-1 text-[10px] font-extrabold uppercase tracking-wider"
                style={{ color: "var(--ink-faint)" }}>Feed</h3>
            <div style={{ borderTop: "var(--line-width) solid var(--line)" }}>
              <Row label="Cards seen" value={stats.cards.seen} />
              <Row label="Total views" value={stats.cards.views} />
              <Row label="Cards mastered" value={stats.cards.mastered} />
            </div>
          </section>
        </>
      )}
    </div>
  );
}

function ManageTab({ profile, onSaved }: {
  profile: ProfileInfo | null;
  onSaved: (p: ProfileInfo) => void;
}) {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [pwBusy, setPwBusy] = useState(false);
  const [pwMessage, setPwMessage] = useState("");
  const [pwError, setPwError] = useState("");

  useEffect(() => {
    if (!profile) return;
    setName(profile.display_name || "");
    setPhone(profile.phone || "");
  }, [profile]);

  const field = {
    background: "var(--surface-sunk)",
    border: "var(--line-width) solid var(--line)",
    color: "var(--ink)",
  };

  const saveDetails = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true); setError(""); setSaved(false);
    try {
      onSaved(await updateProfile({ display_name: name.trim(), phone: phone.trim() }));
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save");
    } finally {
      setBusy(false);
    }
  };

  const savePassword = async (event: React.FormEvent) => {
    event.preventDefault();
    setPwError(""); setPwMessage("");

    // Checked here as well as server-side: a mismatch is the one error
    // worth catching before a round trip, since the user has to retype
    // both fields either way.
    if (next !== confirm) {
      setPwError("Those two passwords do not match");
      return;
    }

    setPwBusy(true);
    try {
      const tokens = await changePassword(current, next);
      // Stored immediately: the change invalidated the old tokens, so
      // without this the next request signs the user out.
      storeSession(tokens);
      setPwMessage("Password changed. Other devices have been signed out.");
      setCurrent(""); setNext(""); setConfirm("");
    } catch (err) {
      setPwError(err instanceof Error ? err.message : "Could not change password");
    } finally {
      setPwBusy(false);
    }
  };

  return (
    <div className="space-y-5">
      <form onSubmit={saveDetails} className="space-y-2">
        <h3 className="text-[10px] font-extrabold uppercase tracking-wider"
            style={{ color: "var(--ink-faint)" }}>Your details</h3>

        <label className="block">
          <span className="mb-1 block text-[11px] font-semibold"
                style={{ color: "var(--ink-soft)" }}>Name</span>
          <input value={name} onChange={(e) => setName(e.target.value)}
                 maxLength={120} autoComplete="name"
                 className="min-h-11 w-full rounded-[var(--radius)] px-3 text-sm outline-none"
                 style={field} />
        </label>

        <label className="block">
          <span className="mb-1 block text-[11px] font-semibold"
                style={{ color: "var(--ink-soft)" }}>Phone</span>
          <input value={phone} onChange={(e) => setPhone(e.target.value)}
                 maxLength={32} inputMode="tel" autoComplete="tel"
                 placeholder="+91 …"
                 className="min-h-11 w-full rounded-[var(--radius)] px-3 text-sm outline-none"
                 style={field} />
          <span className="mt-1 block text-[10px]" style={{ color: "var(--ink-faint)" }}>
            Shown on your profile only. Not used for sign-in or recovery.
          </span>
        </label>

        <p className="text-[10px]" style={{ color: "var(--ink-faint)" }}>
          Email is fixed: it is what Google sign-in matches on, so changing
          it here would detach your account.
        </p>

        {error && (
          <p className="text-[11px] font-semibold" style={{ color: "var(--ink)" }}>
            {error}
          </p>
        )}
        {saved && (
          <p className="text-[11px] font-semibold" style={{ color: "var(--ink-faint)" }}>
            Saved.
          </p>
        )}

        <button type="submit" disabled={busy}
                className="flex min-h-10 w-full items-center justify-center gap-1.5 rounded-[var(--radius-pill)] text-[12px] font-bold disabled:opacity-50"
                style={{ background: "var(--accent)", color: "var(--ink)",
                         border: "var(--line-width) solid var(--line)" }}>
          {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          Save details
        </button>
      </form>

      <form onSubmit={savePassword} className="space-y-2"
            style={{ borderTop: "var(--line-width) solid var(--line)",
                     paddingTop: "1rem" }}>
        <h3 className="flex items-center gap-1.5 text-[10px] font-extrabold uppercase tracking-wider"
            style={{ color: "var(--ink-faint)" }}>
          <KeyRound className="h-3 w-3" />
          {profile?.has_password ? "Change password" : "Set a password"}
        </h3>

        {profile && !profile.has_password && (
          <p className="text-[11px]" style={{ color: "var(--ink-soft)" }}>
            You sign in with Google. Setting a password adds a second way
            in; Google keeps working either way.
          </p>
        )}

        {profile?.has_password && (
          <label className="block">
            <span className="mb-1 block text-[11px] font-semibold"
                  style={{ color: "var(--ink-soft)" }}>Current password</span>
            <input type="password" value={current} required
                   onChange={(e) => setCurrent(e.target.value)}
                   autoComplete="current-password"
                   className="min-h-11 w-full rounded-[var(--radius)] px-3 text-sm outline-none"
                   style={field} />
          </label>
        )}

        <label className="block">
          <span className="mb-1 block text-[11px] font-semibold"
                style={{ color: "var(--ink-soft)" }}>New password</span>
          <input type="password" value={next} required minLength={8}
                 onChange={(e) => setNext(e.target.value)}
                 autoComplete="new-password"
                 className="min-h-11 w-full rounded-[var(--radius)] px-3 text-sm outline-none"
                 style={field} />
          <span className="mt-1 block text-[10px]" style={{ color: "var(--ink-faint)" }}>
            At least 8 characters.
          </span>
        </label>

        <label className="block">
          <span className="mb-1 block text-[11px] font-semibold"
                style={{ color: "var(--ink-soft)" }}>Confirm new password</span>
          <input type="password" value={confirm} required
                 onChange={(e) => setConfirm(e.target.value)}
                 autoComplete="new-password"
                 className="min-h-11 w-full rounded-[var(--radius)] px-3 text-sm outline-none"
                 style={field} />
        </label>

        {pwError && (
          <p className="rounded-[var(--radius)] px-3 py-2 text-[11px] font-semibold"
             style={{ background: "var(--danger)", color: "var(--ink)",
                      border: "var(--line-width) solid var(--line)" }}>
            {pwError}
          </p>
        )}
        {pwMessage && (
          <p className="text-[11px] font-semibold" style={{ color: "var(--ink-faint)" }}>
            {pwMessage}
          </p>
        )}

        <button type="submit" disabled={pwBusy}
                className="flex min-h-10 w-full items-center justify-center gap-1.5 rounded-[var(--radius-pill)] text-[12px] font-bold disabled:opacity-50"
                style={{ background: "var(--surface-sunk)", color: "var(--ink)",
                         border: "var(--line-width) solid var(--line)" }}>
          {pwBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  : <KeyRound className="h-3.5 w-3.5" />}
          {profile?.has_password ? "Change password" : "Set password"}
        </button>
      </form>
    </div>
  );
}
