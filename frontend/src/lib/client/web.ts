/**
 * The single ApiClient the web app shares.
 *
 * A module-level instance rather than React context: the old code
 * patched `window.fetch`, so every call site already assumed one
 * implicit client, and threading a context through 27 files would be a
 * larger change than this refactor needs. The constructor argument is
 * still there, so a test or a second platform can build its own.
 */

import { ApiClient } from "./transport";
import { WebTokenStore } from "./web-storage";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

/** Set by AuthProvider once mounted, so a 401 can reach the UI. */
let signedOutHandler: (() => void) | null = null;

export function onSignedOut(handler: () => void): void {
  signedOutHandler = handler;
}

export const tokenStore = new WebTokenStore();

export const api = new ApiClient({
  baseUrl: API_BASE,
  store: tokenStore,
  onSignedOut: () => signedOutHandler?.(),
});

export { API_BASE };
