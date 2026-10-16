"use client";

import React from "react";
import { Loader2 } from "lucide-react";

import { useAuth } from "./AuthProvider";
import SignInScreen from "./SignInScreen";

/**
 * Shows the app to a signed-in account and the sign-in screen otherwise.
 *
 * Gating here rather than per page means a new route is protected by
 * default. The alternative -- remembering to guard each page -- fails
 * quietly, and the failure is an unprotected screen.
 */
export default function AuthGate({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center"
           style={{ background: "var(--canvas)" }}>
        <Loader2 className="h-5 w-5 animate-spin"
                 style={{ color: "var(--ink-faint)" }} />
      </div>
    );
  }

  return user ? <>{children}</> : <SignInScreen />;
}
