"use client";

import React, { useEffect, useMemo, useState } from "react";
import { Loader2, ShieldAlert, Users } from "lucide-react";

import { Panel } from "@/components/Panel";
import { AdminUserRow, fetchAdminUsers } from "@/lib/admin";
import UserDetail from "./UserDetail";
import UserTable from "./UserTable";

/**
 * The admin portal: every account, and one account's analytics on click.
 *
 * Owns the fetch and the selection; the table renders rows and the
 * dialog renders one account. Splitting it this way means the drill-down
 * can later become its own route without touching the list.
 */

/** Instance-wide totals, derived from the rows already fetched rather
 *  than a second endpoint: the list is the whole population, so the
 *  aggregate is a reduce, not a query. */
function Totals({ users }: { users: AdminUserRow[] }) {
  const t = useMemo(() => {
    const attempts = users.reduce((n, u) => n + u.attempts, 0);
    const correct = users.reduce((n, u) => n + u.correct, 0);
    return {
      total: users.length,
      active7d: users.filter((u) => u.attempts_last_7d > 0).length,
      // Accounts that signed in but never answered anything -- the
      // drop-off this page is most likely to be opened to explain.
      idle: users.filter((u) => u.attempts === 0).length,
      attempts,
      accuracy: attempts ? Math.round((correct / attempts) * 1000) / 10 : null,
    };
  }, [users]);

  const cells: { label: string; value: React.ReactNode }[] = [
    { label: "Accounts", value: t.total },
    { label: "Active this week", value: t.active7d },
    { label: "Never answered", value: t.idle },
    { label: "Questions answered", value: t.attempts },
    { label: "Overall accuracy", value: t.accuracy === null ? "--" : `${t.accuracy}%` },
  ];

  return (
    <Panel size="sm">
      <div className="grid grid-cols-2 gap-x-4 gap-y-2.5 sm:grid-cols-3 lg:grid-cols-5">
        {cells.map((c) => (
          <div key={c.label}>
            <div className="text-lg font-extrabold leading-none" style={{ color: "var(--ink)" }}>
              {c.value}
            </div>
            <div
              className="mt-1 text-[10px] font-bold uppercase tracking-wider"
              style={{ color: "var(--ink-faint)" }}
            >
              {c.label}
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

export default function UsersOverview() {
  const [users, setUsers] = useState<AdminUserRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<AdminUserRow | null>(null);

  useEffect(() => {
    let live = true;
    fetchAdminUsers()
      .then((d) => { if (live) setUsers(d.items); })
      .catch((e) => {
        if (live) {
          setError(
            e instanceof Error ? e.message : "Could not load the account list",
          );
        }
      });
    return () => { live = false; };
  }, []);

  if (error) {
    return (
      <Panel>
        <div className="flex items-start gap-2.5">
          <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "var(--ink)" }} />
          <div>
            <p className="text-[13px] font-bold" style={{ color: "var(--ink)" }}>
              {error}
            </p>
            <p className="mt-1 text-[12px]" style={{ color: "var(--ink-soft)" }}>
              This page is admin-only. The server checks the role on every
              request, so a student account cannot read it even with the
              link.
            </p>
          </div>
        </div>
      </Panel>
    );
  }

  if (!users) {
    return (
      <div className="flex justify-center py-16">
        <Loader2 className="h-5 w-5 animate-spin" style={{ color: "var(--ink-faint)" }} />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <header className="flex items-center gap-2.5">
        <span
          className="flex h-8 w-8 items-center justify-center rounded-[var(--radius)]"
          style={{
            background: "var(--accent)",
            color: "var(--ink)",
            border: "var(--line-width) solid var(--line)",
          }}
        >
          <Users className="h-4 w-4" />
        </span>
        <div>
          <h1 className="text-lg font-extrabold sm:text-xl" style={{ color: "var(--ink)" }}>
            Users
          </h1>
          <p className="text-[11px]" style={{ color: "var(--ink-faint)" }}>
            Click a row for that account&apos;s analytics
          </p>
        </div>
      </header>

      <Totals users={users} />

      <UserTable users={users} onSelect={setSelected} />

      {selected && (
        /* Keyed by id so selecting another row remounts rather than
           reusing the previous account's loaded state. */
        <UserDetail key={selected.id} user={selected}
                    onClose={() => setSelected(null)} />
      )}
    </div>
  );
}
