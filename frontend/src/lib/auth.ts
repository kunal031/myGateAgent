/**
 * Who is signed in.
 *
 * The token plumbing lives in lib/client: this module is the web app's
 * session on top of it -- sign-in, Google's redirect dance, and the
 * browser-only bits (window.location, the URL fragment) that a React
 * Native app replaces with its own.
 *
 * The previous version reassigned `window.fetch` to attach the token.
 * That is gone. Every call now goes through the shared ApiClient, which
 * attaches it explicitly and refreshes on a 401 -- the same behaviour,
 * but visible, testable, and portable to a platform with no `window`.
 */

import { api, tokenStore, onSignedOut, API_BASE } from "./client/web";

export { onSignedOut };

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

/** Tokens are stored through the client's TokenStore, so a React
 *  Native app swaps localStorage for SecureStore without touching this. */
export const accessToken = () => tokenStore.getAccessToken();
export const refreshToken = () => tokenStore.getRefreshToken();

/** Takes only the tokens, so the OAuth callback -- which receives tokens
 *  without a user object -- can use it and then fetch the user. */
export function storeSession(
  session: Pick<AuthSession, "access_token" | "refresh_token">,
): Promise<void> {
  return tokenStore.setTokens({
    access: session.access_token,
    refresh: session.refresh_token,
  });
}

export function clearSession(): Promise<void> {
  return tokenStore.clear();
}

/** Sign in, and keep the session. `anonymous` because these run before a
 *  token exists and must not trigger a refresh. */
async function authenticate(
  path: string, body: unknown,
): Promise<AuthSession> {
  const session = await api.request<AuthSession>(path, {
    method: "POST", body, anonymous: true,
  });
  await storeSession(session);
  return session;
}

export const login = (email: string, password: string) =>
  authenticate("/api/auth/login", { email, password });

export const register = (
  email: string, password: string, display_name: string,
) => authenticate("/api/auth/register", { email, password, display_name });

/** Whether this deployment has Google sign-in configured. */
export async function googleEnabled(): Promise<boolean> {
  try {
    const config = await api.request<{ enabled?: boolean }>(
      "/api/auth/google/config", { anonymous: true },
    );
    return Boolean(config?.enabled);
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
  // Best effort: the server bumps token_version and revokes the session
  // rows, but a failed call must still clear this device.
  try {
    await api.post("/api/auth/logout");
  } catch {
    // Offline, or the token already expired. Clearing below is what
    // actually signs this device out.
  }
  await clearSession();
}

export async function fetchMe(): Promise<AuthUser | null> {
  if (!(await tokenStore.getAccessToken())) return null;
  try {
    return await api.get<AuthUser>("/api/auth/me");
  } catch {
    return null;
  }
}
