"use client";

import React, { useEffect, useRef, useState } from "react";
import { ChevronRight, LogOut, Settings, User } from "lucide-react";

import { useRouter } from "next/navigation";

import { useAuth } from "../auth/AuthProvider";

type View = "closed" | "menu";

/**
 * The avatar button, and the menu behind it.
 *
 * Three choices, as asked: see info, manage profile, sign out. The menu is
 * deliberately a separate step rather than opening straight into the
 * profile -- sign out sits here, and a destructive action reached in one
 * tap from a header icon is easy to hit by accident on a phone.
 */
export default function ProfileMenu({ placement = "below" }: {
  /** "above" for the sidebar foot, where a menu below would open
   *  off the bottom of the viewport. */
  placement?: "below" | "above";
} = {}) {
  const { user, signOut } = useAuth();
  const router = useRouter();
  const [view, setView] = useState<View>("closed");
  const containerRef = useRef<HTMLDivElement>(null);

  // Close on an outside click or Escape, which is what every other menu
  // on the platform does; without it the menu traps taps on mobile.
  useEffect(() => {
    if (view !== "menu") return;

    const onPointerDown = (event: MouseEvent | TouchEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        setView("closed");
      }
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setView("closed");
    };

    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("touchstart", onPointerDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("touchstart", onPointerDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [view]);

  if (!user) return null;

  const initials = (user.display_name || user.email)
    .split(/[\s@._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");

  const item = {
    background: "transparent",
    color: "var(--ink)",
  };

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setView(view === "menu" ? "closed" : "menu")}
        aria-label="Your profile"
        aria-expanded={view === "menu"}
        className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-[var(--radius-pill)] text-[12px] font-extrabold"
        style={{
          background: "var(--accent)",
          color: "var(--ink)",
          border: "var(--line-width) solid var(--line)",
        }}
      >
        {user.avatar_url ? (
          // Plain img, not next/image: the URL is Google's and expires, so
          // the optimiser would cache a link that stops resolving.
          // eslint-disable-next-line @next/next/no-img-element
          <img src={user.avatar_url} alt=""
               className="h-full w-full object-cover" />
        ) : (
          initials || <User className="h-4 w-4" />
        )}
      </button>

      {view === "menu" && (
        <div
          role="menu"
          className={`absolute right-0 z-50 w-60 overflow-hidden rounded-[var(--radius-lg)] py-1 ${
            placement === "above" ? "bottom-12" : "top-12"
          }`}
          style={{
            background: "var(--surface)",
            border: "var(--line-width) solid var(--line)",
            boxShadow: "var(--shadow)",
          }}
        >
          <div className="px-3 py-2"
               style={{ borderBottom: "var(--line-width) solid var(--line)" }}>
            <p className="truncate text-[13px] font-bold" style={{ color: "var(--ink)" }}>
              {user.display_name || "Your account"}
            </p>
            <p className="truncate text-[11px]" style={{ color: "var(--ink-faint)" }}>
              {user.email}
            </p>
            {user.role === "admin" && (
              <span className="mt-1 inline-block rounded-[var(--radius-pill)] px-1.5 py-0.5 text-[9px] font-extrabold uppercase tracking-wider"
                    style={{ background: "var(--accent)", color: "var(--ink)",
                             border: "var(--line-width) solid var(--line)" }}>
                admin
              </span>
            )}
          </div>

          <button
            type="button" role="menuitem" style={item}
            onClick={() => { setView("closed"); router.push("/profile"); }}
            className="flex w-full items-center gap-2.5 px-3 py-2.5 text-left text-[13px] font-semibold hover:opacity-70"
          >
            <User className="h-4 w-4" />
            See info
            <ChevronRight className="ml-auto h-3.5 w-3.5"
                          style={{ color: "var(--ink-faint)" }} />
          </button>

          <button
            type="button" role="menuitem" style={item}
            onClick={() => { setView("closed"); router.push("/profile?tab=manage"); }}
            className="flex w-full items-center gap-2.5 px-3 py-2.5 text-left text-[13px] font-semibold hover:opacity-70"
          >
            <Settings className="h-4 w-4" />
            Manage profile
            <ChevronRight className="ml-auto h-3.5 w-3.5"
                          style={{ color: "var(--ink-faint)" }} />
          </button>

          <div style={{ borderTop: "var(--line-width) solid var(--line)" }}>
            <button
              type="button" role="menuitem"
              onClick={() => { setView("closed"); void signOut(); }}
              className="flex w-full items-center gap-2.5 px-3 py-2.5 text-left text-[13px] font-semibold hover:opacity-70"
              style={{ color: "var(--danger-ink, var(--ink))" }}
            >
              <LogOut className="h-4 w-4" />
              Sign out
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
