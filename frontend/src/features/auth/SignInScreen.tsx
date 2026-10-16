"use client";

import React, { useState } from "react";
import { Loader2, LogIn } from "lucide-react";

import { useAuth } from "./AuthProvider";

/**
 * Sign in, or create the first account.
 *
 * Registration is offered rather than hidden because the first account to
 * exist becomes the admin -- without it a fresh deployment has no way in.
 */
export default function SignInScreen() {
  const { signIn, signUp } = useAuth();
  const [mode, setMode] = useState<"in" | "up">("in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

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
