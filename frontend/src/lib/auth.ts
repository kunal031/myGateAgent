/**
 * Who is signed in, and attaching that to every request.
 *
 * There are 37 fetch calls across three modules and no shared wrapper, so
 * rather than editing each one this installs an interceptor: the token is
 * attached to API requests centrally, and an expired one is refreshed once
 * and the request retried. Doing it per call site would mean 37 chances to
 * forget, and the symptom of forgetting is a 401 on one screen only.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

const ACCESS_KEY = "gm.access";
const REFRESH_KEY = "gm.refresh";

/** Captured before the interceptor replaces window.fetch, so calls made
 *  through it do not recurse into themselves. Must be declared before any
 *  function that uses it runs -- const is not hoisted. */
const originalFetch: typeof fetch =
  typeof window === "undefined" ? fetch : window.fetch.bind(window);

export interface AuthUser {
  id: number;
  email: string;
  display_name: string;
  role: "student" | "admin";
}

export interface AuthSession {
  user: AuthUser;
  access_token: string;
  refresh_token: string;
}

/** Reading storage can throw in private mode, so every access is guarded. */
function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string | null): void {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    // Private mode or blocked storage: the session lasts this page only.
  }
}

export const accessToken = () => read(ACCESS_KEY);
export const refreshToken = () => read(REFRESH_KEY);

export function storeSession(session: AuthSession): void {
  write(ACCESS_KEY, session.access_token);
  write(REFRESH_KEY, session.refresh_token);
}

export function clearSession(): void {
  write(ACCESS_KEY, null);
  write(REFRESH_KEY, null);
}

async function post<T>(path: string, body: unknown): Promise<T> {
  // Deliberately the raw fetch: these run before a token exists, and the
  // interceptor would otherwise try to refresh its way into a loop.
  const res = await originalFetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? "Request failed");
  }
  return res.json();
}

export const login = (email: string, password: string) =>
  post<AuthSession>("/api/auth/login", { email, password });

export const register = (
  email: string, password: string, display_name: string,
) => post<AuthSession>("/api/auth/register", { email, password, display_name });

export async function logout(): Promise<void> {
  const token = accessToken();
  if (token) {
    await originalFetch(`${API_BASE}/api/auth/logout`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    }).catch(() => {});
  }
  clearSession();
}

export async function fetchMe(): Promise<AuthUser | null> {
  const token = accessToken();
  if (!token) return null;
  const res = await originalFetch(`${API_BASE}/api/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return res.ok ? res.json() : null;
}

//: Concurrent 401s share one refresh rather than each starting their own,
//: which would invalidate each other's tokens and sign the user out.
let refreshing: Promise<boolean> | null = null;

async function refreshSession(): Promise<boolean> {
  const token = refreshToken();
  if (!token) return false;
  try {
    const session = await post<AuthSession>("/api/auth/refresh", {
      refresh_token: token,
    });
    storeSession(session);
    return true;
  } catch {
    clearSession();
    return false;
  }
}

let installed = false;

/** Attach the token to API calls, refreshing once on expiry. */
export function installAuthInterceptor(onSignedOut: () => void): void {
  if (installed || typeof window === "undefined") return;
  installed = true;

  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    // Only our own API, and never the auth routes themselves.
    if (!url.startsWith(API_BASE) || url.includes("/api/auth/")) {
      return originalFetch(input, init);
    }

    const withToken = (token: string | null): RequestInit => {
      if (!token) return init ?? {};
      const headers = new Headers(init?.headers);
      headers.set("Authorization", `Bearer ${token}`);
      return { ...init, headers };
    };

    let response = await originalFetch(input, withToken(accessToken()));
    if (response.status !== 401) return response;

    // One refresh, shared by everything that got a 401 at once.
    refreshing = refreshing ?? refreshSession().finally(() => {
      refreshing = null;
    });
    const renewed = await refreshing;
    if (!renewed) {
      onSignedOut();
      return response;
    }

    response = await originalFetch(input, withToken(accessToken()));
    if (response.status === 401) onSignedOut();
    return response;
  };
}
