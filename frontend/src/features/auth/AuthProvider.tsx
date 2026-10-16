"use client";

import React, {
  createContext, useCallback, useContext, useEffect, useState,
} from "react";

import {
  AuthUser, clearSession, fetchMe, installAuthInterceptor, login as apiLogin,
  logout as apiLogout, register as apiRegister, storeSession,
} from "@/lib/auth";

interface AuthState {
  user: AuthUser | null;
  /** True until the stored token has been checked, so nothing flashes. */
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, name: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const Context = createContext<AuthState | null>(null);

/**
 * Holds the signed-in account and installs the fetch interceptor.
 *
 * `loading` exists so the app does not render a signed-out view for a
 * frame before the stored token is validated -- on a mobile connection
 * that flash is long enough to look like being logged out.
 */
export default function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  const handleSignedOut = useCallback(() => {
    clearSession();
    setUser(null);
  }, []);

  useEffect(() => {
    installAuthInterceptor(handleSignedOut);
    let cancelled = false;
    fetchMe()
      .then((me) => !cancelled && setUser(me))
      .catch(() => {})
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [handleSignedOut]);

  const signIn = useCallback(async (email: string, password: string) => {
    const session = await apiLogin(email, password);
    storeSession(session);
    setUser(session.user);
  }, []);

  const signUp = useCallback(
    async (email: string, password: string, name: string) => {
      const session = await apiRegister(email, password, name);
      storeSession(session);
      setUser(session.user);
    },
    [],
  );

  const signOut = useCallback(async () => {
    await apiLogout();
    setUser(null);
  }, []);

  return (
    <Context.Provider value={{ user, loading, signIn, signUp, signOut }}>
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
