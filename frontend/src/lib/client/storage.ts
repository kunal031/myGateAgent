/**
 * Where tokens live, as an interface rather than a global.
 *
 * The web app reads localStorage; React Native has no such thing and
 * uses AsyncStorage or expo-secure-store, which are async. The interface
 * is therefore async everywhere -- a sync one would be impossible to
 * implement on the platform that needs it most, and `await` over a
 * synchronous localStorage read costs nothing.
 *
 * Keeping this a parameter is also what makes httpOnly cookies possible
 * later without touching any call site: a CookieTokenStore simply
 * returns null for the refresh token and lets the browser send it.
 */

export interface TokenStore {
  getAccessToken(): Promise<string | null>;
  getRefreshToken(): Promise<string | null>;
  /** Both tokens together: a refresh returns a new pair, and storing
   *  them separately leaves a window where they disagree. */
  setTokens(tokens: { access: string; refresh: string }): Promise<void>;
  clear(): Promise<void>;
}

/** Holds tokens in memory only. The default when nothing is supplied,
 *  and the right choice for a server-side render, where there is no
 *  per-user storage and leaking one request's token into another's would
 *  be the worst kind of bug. */
export class MemoryTokenStore implements TokenStore {
  private access: string | null = null;
  private refresh: string | null = null;

  async getAccessToken() {
    return this.access;
  }

  async getRefreshToken() {
    return this.refresh;
  }

  async setTokens(tokens: { access: string; refresh: string }) {
    this.access = tokens.access;
    this.refresh = tokens.refresh;
  }

  async clear() {
    this.access = null;
    this.refresh = null;
  }
}
