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
  avatar_url?: string | null;
  /** False for an account that only signs in with Google. */
  has_password?: boolean;
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

/** Takes only the tokens, so the OAuth callback -- which receives tokens
 *  without a user object -- can use it and then fetch the user. */
export function storeSession(
  session: Pick<AuthSession, "access_token" | "refresh_token">,
): void {
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

/** Whether this deployment has Google sign-in configured. */
export async function googleEnabled(): Promise<boolean> {
  try {
    const res = await originalFetch(`${API_BASE}/api/auth/google/config`);
    if (!res.ok) return false;
    return Boolean((await res.json())?.enabled);
  } catch {
    return false;
  }
}

/** Hand the browser to Google. A full navigation, not fetch: the consent
 *  screen is a page the user interacts with, and XHR cannot show it. */
export function startGoogleSignIn(next = ""): void {
  const query = next ? `?next=${encodeURIComponent(next)}` : "";
  window.location.href = `${API_BASE}/api/auth/google/start${query}`;
}

/**
 * Read the tokens the callback left in the URL fragment.
 *
 * The fragment is used rather than the query string because it is never
 * transmitted to a server -- no access log, proxy or Referer header ever
 * sees these tokens. It is cleared from the address bar immediately after
 * reading so the back button cannot resurrect them.
 */
export function consumeOAuthFragment():
  { session: Pick<AuthSession, "access_token" | "refresh_token">; next: string }
  | { error: string }
  | null {
  if (typeof window === "undefined") return null;

  const error = new URLSearchParams(window.location.search).get("error");
  if (error) return { error };

  const fragment = window.location.hash.replace(/^#/, "");
  if (!fragment) return null;

  const params = new URLSearchParams(fragment);
  const access = params.get("access_token");
  const refresh = params.get("refresh_token");
  if (!access || !refresh) return null;

  // Drop the tokens from the visible URL before anything else happens.
  window.history.replaceState({}, "", window.location.pathname);

  return {
    session: { access_token: access, refresh_token: refresh },
    next: params.get("next") || "/",
  };
}

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
