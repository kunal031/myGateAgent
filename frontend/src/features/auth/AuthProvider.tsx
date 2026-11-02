"use client";

import React, {
  createContext, useCallback, useContext, useEffect, useState,
} from "react";

import {
  AuthUser, clearSession, consumeOAuthFragment, fetchMe,
  login as apiLogin, logout as apiLogout, onSignedOut,
  register as apiRegister, startGoogleSignIn, storeSession,
} from "@/lib/auth";

interface AuthState {
  user: AuthUser | null;
  /** True until the stored token has been checked, so nothing flashes. */
  loading: boolean;
  /** Set when a Google sign-in came back with a failure. */
  oauthError: string;
  /** Where a completed Google sign-in was originally headed, if anywhere. */
  oauthNext: string;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, name: string) => Promise<void>;
  signInWithGoogle: () => void;
  signOut: () => Promise<void>;
}

const Context = createContext<AuthState | null>(null);

/**
 * Holds the signed-in account, and tells the API client where to report
 * a dead session.
 *
 * `loading` exists so the app does not render a signed-out view for a
 * frame before the stored token is validated -- on a mobile connection
 * that flash is long enough to look like being logged out.
 */
export default function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [oauthError, setOauthError] = useState("");
  const [oauthNext, setOauthNext] = useState("");

  const handleSignedOut = useCallback(() => {
    void clearSession();
    setUser(null);
  }, []);

  useEffect(() => {
    onSignedOut(handleSignedOut);
    let cancelled = false;

    // A Google sign-in returns here with tokens in the URL fragment.
    // Awaited before fetchMe, so the first /me call carries the new
    // token rather than failing and, on a slow connection, bouncing the
    // user back to the sign-in screen they just left. Storage is async
    // now (React Native's is), so this has to be a chain rather than
    // two statements.
    const returned = consumeOAuthFragment();
    const adopted =
      returned && !("error" in returned)
        ? storeSession(returned.session).then(() => {
            if (!cancelled) setOauthNext(returned.next);
          })
        : Promise.resolve();

    if (returned && "error" in returned) setOauthError(returned.error);

    adopted
      .then(() => fetchMe())
      .then((me) => !cancelled && setUser(me))
      .catch(() => {})
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [handleSignedOut]);

  const signIn = useCallback(async (email: string, password: string) => {
    // authenticate() already persisted the tokens.
    const session = await apiLogin(email, password);
    setUser(session.user);
  }, []);

  const signUp = useCallback(
    async (email: string, password: string, name: string) => {
      const session = await apiRegister(email, password, name);
      setUser(session.user);
    },
    [],
  );

  const signInWithGoogle = useCallback(() => {
    setOauthError("");
    // Leaves the page entirely, so there is no promise to await and no
    // state to set afterwards -- the AuthProvider that handles the return
    // is a fresh one on the page Google redirects back to.
    startGoogleSignIn(window.location.pathname);
  }, []);

  const signOut = useCallback(async () => {
    await apiLogout();
    setUser(null);
  }, []);

  return (
    <Context.Provider value={{
      user, loading, oauthError, oauthNext,
      signIn, signUp, signInWithGoogle, signOut,
    }}>
      {children}
    </Context.Provider>
  );
}

export function useAuth(): AuthState {
  const value = useContext(Context);
  if (value === null) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return value;
}
