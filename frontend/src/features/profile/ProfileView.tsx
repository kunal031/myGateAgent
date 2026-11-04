"use client";

import React, { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, Loader2 } from "lucide-react";

import {
  ProfileInfo, ProfileStats, fetchProfile, fetchProfileStats,
} from "@/lib/api";

import { InfoTab, ManageTab } from "./ProfileTabs";

type Tab = "info" | "manage";

/**
 * The profile page: your details and numbers, or the forms to change them.
 *
 * The tab lives in the query string rather than in state, so the two
 * halves are separately linkable -- the sidebar menu sends you straight
 * to ?tab=manage -- and the back button steps between them as expected.
 */
export default function ProfileView() {
  const router = useRouter();
  const params = useSearchParams();
  const tab: Tab = params.get("tab") === "manage" ? "manage" : "info";

  const [profile, setProfile] = useState<ProfileInfo | null>(null);
  const [stats, setStats] = useState<ProfileStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    Promise.allSettled([fetchProfile(), fetchProfileStats()])
      .then(([p, s]) => {
        if (cancelled) return;
        if (p.status === "fulfilled") setProfile(p.value);
        if (s.status === "fulfilled") setStats(s.value);
      })
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, []);

  const select = (next: Tab) => {
    // replace, not push: flipping a tab should not stack history entries
    // that the back button then has to walk through to leave the page.
    router.replace(next === "info" ? "/profile" : "/profile?tab=manage");
  };

  return (
    /* space-y-5 and no max-width, matching feed, quiz, test and
       analytics. max-w-2xl centred this inside a shell that already
       pads, which left a wide band of empty space between the sidebar
       and the content that no other page has -- the same problem
       analytics already fixed. */
    <div className="space-y-5">
      <header className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => router.back()}
          aria-label="Go back"
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[var(--radius)]"
          style={{
            border: "var(--line-width) solid var(--line)",
            color: "var(--ink)",
          }}
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <div className="min-w-0">
          <h1 className="text-lg font-extrabold leading-tight"
              style={{ color: "var(--ink)" }}>
            {profile?.display_name || "Your account"}
          </h1>
          <p className="truncate text-[12px]" style={{ color: "var(--ink-faint)" }}>
            {profile?.email ?? ""}
          </p>
        </div>
      </header>

      <div className="flex gap-1 rounded-[var(--radius-pill)] p-0.5"
           style={{
             background: "var(--surface-sunk)",
             border: "var(--line-width) solid var(--line)",
             width: "fit-content",
           }}>
        {(["info", "manage"] as Tab[]).map((value) => (
          <button
            key={value}
            type="button"
            onClick={() => select(value)}
            className="rounded-[var(--radius-pill)] px-4 py-1.5 text-[11px] font-extrabold uppercase tracking-wider"
            style={tab === value
              ? { background: "var(--accent)", color: "var(--ink)" }
              : { background: "transparent", color: "var(--ink-faint)" }}
          >
            {value === "info" ? "Info" : "Manage profile"}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-5 w-5 animate-spin"
                   style={{ color: "var(--ink-faint)" }} />
        </div>
      ) : (
        <section
          className="rounded-[var(--radius-lg)] p-4"
          style={{
            background: "var(--surface)",
            border: "var(--line-width) solid var(--line)",
          }}
        >
          {tab === "info"
            ? <InfoTab profile={profile} stats={stats} />
            : (
              // Keyed on the account so the form remounts once the
              // profile has loaded: its fields are initialised from the
              // prop rather than synced in an effect.
              <ManageTab key={profile?.id ?? "pending"}
                         profile={profile} onSaved={setProfile} />
            )}
        </section>
      )}
    </div>
  );
}
