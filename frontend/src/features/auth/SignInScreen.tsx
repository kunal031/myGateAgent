"use client";

import React, { useEffect, useState } from "react";
import { Loader2, LogIn } from "lucide-react";

import { googleEnabled } from "@/lib/auth";

import { useAuth } from "./AuthProvider";

/** Google's mark, inlined rather than loaded from their CDN: one fewer
 *  third-party request, and the button renders before the network does. */
function GoogleMark() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#4285F4" d="M45.1 24.5c0-1.6-.1-2.8-.4-4H24v7.6h11.9c-.2 2-1.5 5-4.4 7l-.1.3 6.4 5 .4.1c4.1-3.8 6.9-9.3 6.9-16z" />
      <path fill="#34A853" d="M24 46c5.9 0 10.9-1.9 14.5-5.3l-6.9-5.3c-1.8 1.3-4.3 2.2-7.6 2.2-5.8 0-10.7-3.8-12.4-9.1l-.3.1-6.6 5-.1.3C8.1 41 15.5 46 24 46z" />
      <path fill="#FBBC05" d="M11.6 28.5c-.5-1.4-.7-2.9-.7-4.5s.3-3.1.7-4.5v-.3l-6.8-5.2-.2.1C3 17.1 2 20.4 2 24s1 6.9 2.6 9.9l7-5.4z" />
      <path fill="#EA4335" d="M24 10.2c4.1 0 6.9 1.8 8.5 3.3l6.2-6C34.9 4.1 29.9 2 24 2 15.5 2 8.1 7 4.6 14.1l7 5.4C13.3 14.2 18.2 10.2 24 10.2z" />
    </svg>
  );
}

/**
 * Sign in, or create the first account.
 *
 * Registration is offered rather than hidden because the first account to
 * exist becomes the admin -- without it a fresh deployment has no way in.
 */
export default function SignInScreen() {
  const { signIn, signUp, signInWithGoogle, oauthError } = useAuth();
  const [mode, setMode] = useState<"in" | "up">("in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  // Asked at runtime rather than baked in at build time, so one bundle
  // serves a deployment with Google configured and one without.
  const [googleReady, setGoogleReady] = useState(false);
  useEffect(() => { googleEnabled().then(setGoogleReady); }, []);

  // A failed Google return should be visible on the form it bounced to.
  useEffect(() => { if (oauthError) setError(oauthError); }, [oauthError]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      if (mode === "in") await signIn(email.trim(), password);
      else await signUp(email.trim(), password, name.trim());
    } catch (err) {
      setError(err instanceof Error ? err.message : "That did not work");
      setBusy(false);
    }
  };

  const field = {
    background: "var(--surface-sunk)",
    border: "var(--line-width) solid var(--line)",
    color: "var(--ink)",
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-4"
         style={{ background: "var(--canvas)" }}>
      <form
        onSubmit={submit}
        className="w-full max-w-sm space-y-3 rounded-[var(--radius-lg)] p-6"
        style={{
          background: "var(--surface)",
          border: "var(--line-width) solid var(--line)",
          boxShadow: "var(--shadow)",
        }}
      >
        <div className="mb-4">
          <h1 className="text-lg font-extrabold" style={{ color: "var(--ink)" }}>
            GateMaster
          </h1>
          <p className="text-[12px] font-semibold" style={{ color: "var(--ink-faint)" }}>
            {mode === "in" ? "Sign in to continue" : "Create your account"}
          </p>
        </div>

        {googleReady && (
          <>
            <button
              type="button"
              onClick={signInWithGoogle}
              className="flex min-h-11 w-full items-center justify-center gap-2 rounded-[var(--radius-pill)] text-[13px] font-bold"
              style={{
                background: "var(--surface)",
                color: "var(--ink)",
                border: "var(--line-width) solid var(--line)",
              }}
            >
              <GoogleMark />
              Continue with Google
            </button>

            <div className="flex items-center gap-2 py-1">
              <span className="h-px flex-1" style={{ background: "var(--line)" }} />
              <span className="text-[10px] font-extrabold uppercase tracking-wider"
                    style={{ color: "var(--ink-faint)" }}>or</span>
              <span className="h-px flex-1" style={{ background: "var(--line)" }} />
            </div>
          </>
        )}

        {mode === "up" && (
          <label className="block">
            <span className="mb-1 block text-[10px] font-extrabold uppercase tracking-wider"
                  style={{ color: "var(--ink-faint)" }}>Name</span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoComplete="name"
              className="min-h-11 w-full rounded-[var(--radius)] px-3 text-sm outline-none"
              style={field}
            />
          </label>
        )}

        <label className="block">
          <span className="mb-1 block text-[10px] font-extrabold uppercase tracking-wider"
                style={{ color: "var(--ink-faint)" }}>Email</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            required
            className="min-h-11 w-full rounded-[var(--radius)] px-3 text-sm outline-none"
            style={field}
          />
        </label>

        <label className="block">
          <span className="mb-1 block text-[10px] font-extrabold uppercase tracking-wider"
                style={{ color: "var(--ink-faint)" }}>Password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={mode === "in" ? "current-password" : "new-password"}
            required
            minLength={8}
            className="min-h-11 w-full rounded-[var(--radius)] px-3 text-sm outline-none"
            style={field}
          />
          {mode === "up" && (
            <span className="mt-1 block text-[10px]" style={{ color: "var(--ink-faint)" }}>
              At least 8 characters.
            </span>
          )}
        </label>

        {error && (
          <p className="rounded-[var(--radius)] px-3 py-2 text-[12px] font-semibold"
             style={{ background: "var(--danger)", color: "var(--ink)",
                      border: "var(--line-width) solid var(--line)" }}>
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={busy}
          className="flex min-h-11 w-full items-center justify-center gap-1.5 rounded-[var(--radius-pill)] text-[13px] font-bold disabled:opacity-50"
          style={{ background: "var(--accent)", color: "var(--ink)",
                   border: "var(--line-width) solid var(--line)" }}
        >
          {busy ? <Loader2 className="h-4 w-4 animate-spin" />
                : <LogIn className="h-4 w-4" />}
          {mode === "in" ? "Sign in" : "Create account"}
        </button>

        <button
          type="button"
          onClick={() => { setMode(mode === "in" ? "up" : "in"); setError(""); }}
          className="w-full text-[11px] font-semibold"
          style={{ color: "var(--ink-faint)" }}
        >
          {mode === "in"
            ? "No account yet? Create one"
            : "Already have an account? Sign in"}
        </button>
      </form>
    </div>
  );
}
