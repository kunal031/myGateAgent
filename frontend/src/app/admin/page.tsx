"use client";

import React from "react";
import Link from "next/link";
import { Loader2, ShieldAlert } from "lucide-react";

import UsersOverview from "@/features/admin/UsersOverview";
import { useAuth } from "@/features/auth/AuthProvider";

/**
 * The admin portal.
 *
 * Sign-in is already handled: AuthGate wraps every route in the root
 * layout, so reaching this component means there is a session. What is
 * left is the role, and the check here is a courtesy -- it renders a
 * readable message instead of a wall of failed requests. The real guard
 * is admin_user on the backend, which reads the role from the database
 * on every request and does not trust the token's claim.
 */
export default function AdminPage() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <Loader2 className="h-5 w-5 animate-spin" style={{ color: "var(--ink-faint)" }} />
      </div>
    );
  }

  if (user?.role !== "admin") {
    return (
      <section
        className="mx-auto max-w-md space-y-2 rounded-[var(--radius-lg)] p-5 text-center"
        style={{
          background: "var(--surface)",
          border: "var(--line-width) solid var(--line)",
        }}
      >
        <ShieldAlert className="mx-auto h-6 w-6" style={{ color: "var(--ink-faint)" }} />
        <h1 className="text-base font-extrabold" style={{ color: "var(--ink)" }}>
          Admins only
        </h1>
        <p className="text-[12px]" style={{ color: "var(--ink-soft)" }}>
          This page lists every account on the instance, so it is limited to
          administrators.
        </p>
        <Link
          href="/feed"
          className="inline-block rounded-[var(--radius-pill)] px-3 py-1.5 text-[12px] font-bold"
          style={{
            background: "var(--accent)",
            color: "var(--accent-ink)",
            border: "var(--line-width) solid var(--line)",
          }}
        >
          Back to feed
        </Link>
      </section>
    );
  }

  return <UsersOverview />;
}
