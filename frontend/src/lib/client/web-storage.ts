/**
 * The browser's TokenStore.
 *
 * Every access is wrapped: localStorage throws in a private window with
 * site data blocked, and a sign-in screen that crashes instead of just
 * failing to persist is worse than one that forgets.
 */

import type { TokenStore } from "./storage";

const ACCESS_KEY = "gm.access";
const REFRESH_KEY = "gm.refresh";

function read(key: string): string | null {
  try {
    return typeof localStorage === "undefined"
      ? null
      : localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string | null): void {
  try {
    if (typeof localStorage === "undefined") return;
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    // Private mode, or storage disabled: the session lasts this page only.
  }
}

export class WebTokenStore implements TokenStore {
  async getAccessToken() {
    return read(ACCESS_KEY);
  }

  async getRefreshToken() {
    return read(REFRESH_KEY);
  }

  async setTokens(tokens: { access: string; refresh: string }) {
    write(ACCESS_KEY, tokens.access);
    write(REFRESH_KEY, tokens.refresh);
  }

  async clear() {
    write(ACCESS_KEY, null);
    write(REFRESH_KEY, null);
  }
}
