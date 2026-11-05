"use client";

import React, { useMemo, useState } from "react";
import { ChevronRight, KeyRound, Search, ShieldCheck } from "lucide-react";

import { AdminUserRow } from "@/lib/admin";

/**
 * The user list: one row per account, sortable, with the drill-down on
 * click.
 *
 * Sorting and filtering are client-side on purpose. The list is every
 * account on the instance -- tens, not thousands -- so a round trip per
 * sort would be slower than the sort and would need four more query
 * parameters on the endpoint to express.
 */

type SortKey = "created_at" | "last_login_at" | "attempts" | "accuracy"
  | "attempts_last_7d" | "email";

const COLUMNS: { key: SortKey; label: string; numeric: boolean }[] = [
  { key: "email", label: "Account", numeric: false },
  { key: "attempts", label: "Answered", numeric: true },
  { key: "accuracy", label: "Accuracy", numeric: true },
  { key: "attempts_last_7d", label: "Last 7d", numeric: true },
  { key: "last_login_at", label: "Last seen", numeric: false },
  { key: "created_at", label: "Joined", numeric: false },
];

/** Short date. The full timestamp is in the drill-down. */
function shortDate(iso: string | null): string {
  if (!iso) return "--";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "--";
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

function relative(iso: string | null): string {
  if (!iso) return "never";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "never";
  const days = Math.floor((Date.now() - then) / 86_400_000);
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 30) return `${days}d ago`;
  return shortDate(iso);
}

export default function UserTable({
  users,
  onSelect,
}: {
  users: AdminUserRow[];
  onSelect: (user: AdminUserRow) => void;
}) {
  const [sort, setSort] = useState<SortKey>("created_at");
  const [asc, setAsc] = useState(false);
  const [query, setQuery] = useState("");

  const rows = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const filtered = needle
      ? users.filter(
          (u) =>
            u.email.toLowerCase().includes(needle)
            || u.display_name.toLowerCase().includes(needle),
        )
      : users;

    const direction = asc ? 1 : -1;
    return [...filtered].sort((a, b) => {
      const l = a[sort];
      const r = b[sort];
      // Nulls last whichever way the sort runs: an account that has
      // never signed in is not "the oldest login".
      if (l === null && r === null) return 0;
      if (l === null) return 1;
      if (r === null) return -1;
      if (typeof l === "number" && typeof r === "number") {
        return (l - r) * direction;
      }
      return String(l).localeCompare(String(r)) * direction;
    });
  }, [users, sort, asc, query]);

  function pick(key: SortKey) {
    if (key === sort) {
      setAsc(!asc);
    } else {
      setSort(key);
      // Numbers and dates are most useful largest-first; names are not.
      setAsc(key === "email");
    }
  }

  return (
    <div className="space-y-2.5">
      <label
        className="flex items-center gap-2 rounded-[var(--radius-pill)] px-3 py-2"
        style={{
          background: "var(--surface-sunk)",
          border: "var(--line-width) solid var(--line)",
        }}
      >
        <Search className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--ink-faint)" }} />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Filter by email or name"
          className="min-w-0 flex-1 bg-transparent text-[12px] outline-none"
          style={{ color: "var(--ink)" }}
        />
        {query && (
          <span className="shrink-0 text-[10px] font-bold" style={{ color: "var(--ink-faint)" }}>
            {rows.length}/{users.length}
          </span>
        )}
      </label>

      {/* Scrolls rather than overflowing: six columns do not fit a
          phone, and the alternative is a card list that loses the
          column comparison this page exists for. */}
      <div
        className="overflow-x-auto rounded-[var(--radius-lg)]"
        style={{
          background: "var(--surface)",
          border: "var(--line-width) solid var(--line)",
        }}
      >
        <table className="w-full border-collapse text-[12px]">
          <thead>
            <tr>
              {COLUMNS.map((col) => (
                <th
                  key={col.key}
                  className={
                    "whitespace-nowrap px-3 py-2.5 font-extrabold "
                    + (col.numeric ? "text-right" : "text-left")
                  }
                  style={{
                    borderBottom: "var(--line-width) solid var(--line)",
                    background: "var(--surface-sunk)",
                    color: "var(--ink-faint)",
                  }}
                >
                  <button
                    type="button"
                    onClick={() => pick(col.key)}
                    className="text-[10px] uppercase tracking-wider hover:opacity-70"
                    style={{ color: sort === col.key ? "var(--ink)" : "inherit" }}
                    aria-label={`Sort by ${col.label}`}
                  >
                    {col.label}
                    {sort === col.key && (asc ? " ↑" : " ↓")}
                  </button>
                </th>
              ))}
              <th
                style={{
                  borderBottom: "var(--line-width) solid var(--line)",
                  background: "var(--surface-sunk)",
                }}
              />
            </tr>
          </thead>
          <tbody>
            {rows.map((u) => (
              <tr
                key={u.id}
                onClick={() => onSelect(u)}
                className="cursor-pointer hover:opacity-80"
                style={{ borderBottom: "var(--line-width) solid var(--line)" }}
              >
                <td className="px-3 py-2.5">
                  <div className="flex items-center gap-2">
                    <div className="min-w-0">
                      <div
                        className="flex items-center gap-1.5 truncate font-bold"
                        style={{ color: "var(--ink)" }}
                      >
                        {u.display_name || u.email.split("@")[0]}
                        {u.role === "admin" && (
                          <ShieldCheck
                            className="h-3 w-3 shrink-0"
                            style={{ color: "var(--accent)" }}
                            aria-label="Admin"
                          />
                        )}
                        {/* How they sign in: the first thing to check
                            when someone cannot get in. */}
                        {u.google_linked && !u.has_password && (
                          <KeyRound
                            className="h-3 w-3 shrink-0"
                            style={{ color: "var(--ink-faint)" }}
                            aria-label="Google only"
                          />
                        )}
                      </div>
                      <div className="truncate text-[11px]" style={{ color: "var(--ink-faint)" }}>
                        {u.email}
                      </div>
                    </div>
                  </div>
                </td>
                <td className="px-3 py-2.5 text-right font-bold" style={{ color: "var(--ink)" }}>
                  {u.attempts}
                </td>
                <td className="px-3 py-2.5 text-right" style={{ color: "var(--ink-soft)" }}>
                  {u.accuracy === null ? "--" : `${u.accuracy}%`}
                </td>
                <td className="px-3 py-2.5 text-right" style={{ color: "var(--ink-soft)" }}>
                  {u.attempts_last_7d || "--"}
                </td>
                <td className="whitespace-nowrap px-3 py-2.5" style={{ color: "var(--ink-soft)" }}>
                  {relative(u.last_login_at)}
                </td>
                <td className="whitespace-nowrap px-3 py-2.5" style={{ color: "var(--ink-faint)" }}>
                  {shortDate(u.created_at)}
                </td>
                <td className="px-2 py-2.5">
                  <ChevronRight className="h-3.5 w-3.5" style={{ color: "var(--ink-faint)" }} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {rows.length === 0 && (
          <div className="px-3 py-8 text-center text-[12px]" style={{ color: "var(--ink-faint)" }}>
            {users.length === 0 ? "No accounts yet." : "No account matches that filter."}
          </div>
        )}
      </div>
    </div>
  );
}
