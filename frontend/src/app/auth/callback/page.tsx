"use client";

import React, { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import { useAuth } from "@/features/auth/AuthProvider";

/**
 * Where Google sends the browser after a successful sign-in.
 *
 * The work is already done by the time this renders: AuthProvider mounts
 * above it, reads the tokens out of the URL fragment and clears them from
 * the address bar. This page only waits for the account to resolve and
 * then gets out of the way.
 *
 * It exists as a route of its own rather than landing on "/" so the
 * redirect URI registered with Google is a stable, single-purpose path --
 * one that cannot collide with a real page's own query parameters.
 */
export default function OAuthCallbackPage() {
  const { user, loading, oauthError, oauthNext } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading || oauthError) return;

    // Only ever a same-origin path. An absolute URL arriving here would
    // make this an open redirect -- somewhere to bounce a victim off a
    // trusted domain -- so anything that is not a plain "/path" is
    // discarded in favour of the home page.
    const target =
      oauthNext.startsWith("/") && !oauthNext.startsWith("//")
        ? oauthNext
        : "/";

    // replace, not push: the callback URL should not sit in history where
    // the back button would return to a spent sign-in.
    router.replace(user ? target : "/");
  }, [loading, user, oauthError, oauthNext, router]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 px-4"
         style={{ background: "var(--canvas)" }}>
      {oauthError ? (
        <p className="max-w-sm text-center text-[13px] font-semibold"
           style={{ color: "var(--ink)" }}>
          {oauthError}
        </p>
      ) : (
        <>
          <Loader2 className="h-5 w-5 animate-spin"
                   style={{ color: "var(--ink-faint)" }} />
          <p className="text-[12px] font-semibold" style={{ color: "var(--ink-faint)" }}>
            Finishing sign-in…
          </p>
        </>
      )}
    </div>
  );
}
