/**
 * One place that talks to the API.
 *
 * This replaces an interceptor that reassigned `window.fetch`. That
 * worked, and it had a real argument behind it -- 48 call sites and no
 * shared wrapper -- but it cannot move to React Native, where there is
 * no `window` to patch, and it makes the token flow invisible: nothing
 * at a call site says a request is authenticated.
 *
 * Everything the platform differs on is a constructor argument:
 *
 *   fetchImpl  the browser's fetch, React Native's, or a stub in tests
 *   store      localStorage, AsyncStorage, SecureStore, or memory
 *   onSignedOut  what to do when the refresh token is finally dead
 *
 * The 401-refresh-retry behaviour is kept, including sharing one refresh
 * between concurrent 401s. With rotation on the server that sharing is
 * no longer just an optimisation: two parallel refreshes would each
 * present the same token, the second would look like a replay, and the
 * account would be signed out of everything. The single-flight promise
 * is what prevents the client from framing itself.
 */

import { MemoryTokenStore, type TokenStore } from "./storage";

export type FetchLike = (
  input: string,
  init?: {
    method?: string;
    headers?: Record<string, string>;
    body?: string | FormData;
    signal?: AbortSignal;
  },
) => Promise<{
  ok: boolean;
  status: number;
  json(): Promise<unknown>;
  text(): Promise<string>;
}>;

export interface ApiClientOptions {
  baseUrl: string;
  store?: TokenStore;
  fetchImpl?: FetchLike;
  /** Called when the session cannot be recovered. */
  onSignedOut?: () => void;
}

/** An API error carrying the status, so a caller can tell "not found"
 *  from "not allowed" without parsing a message. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  /** Serialised as JSON. Use `form` for multipart. */
  body?: unknown;
  form?: FormData;
  query?: Record<string, string | number | boolean | undefined | null>;
  signal?: AbortSignal;
  /** Skips the Authorization header and the refresh retry. For the auth
   *  routes themselves, which would otherwise recurse. */
  anonymous?: boolean;
}

export class ApiClient {
  private readonly baseUrl: string;
  private readonly fetchImpl: FetchLike;
  private readonly onSignedOut?: () => void;
  readonly store: TokenStore;

  //: Concurrent 401s share one refresh. See the note at the top: with
  //: rotation, parallel refreshes look like token theft.
  private refreshing: Promise<boolean> | null = null;

  constructor(options: ApiClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/$/, "");
    this.store = options.store ?? new MemoryTokenStore();
    this.fetchImpl =
      options.fetchImpl ?? (globalThis.fetch as unknown as FetchLike);
    this.onSignedOut = options.onSignedOut;

    if (typeof this.fetchImpl !== "function") {
      throw new Error(
        "No fetch available. Pass fetchImpl explicitly on a platform " +
          "without a global fetch.",
      );
    }
  }

  private url(path: string, query?: RequestOptions["query"]): string {
    const search = new URLSearchParams();
    for (const [key, value] of Object.entries(query ?? {})) {
      // Skipping "all" keeps the filter call sites free of conditionals;
      // it is the sentinel the UI already uses for "no filter".
      if (value === undefined || value === null || value === "" || value === "all") {
        continue;
      }
      search.append(key, String(value));
    }
    const qs = search.toString();
    return `${this.baseUrl}${path}${qs ? `?${qs}` : ""}`;
  }

  private async send(
    path: string,
    options: RequestOptions,
    token: string | null,
  ) {
    const headers: Record<string, string> = {};
    if (token) headers.Authorization = `Bearer ${token}`;

    let body: string | FormData | undefined;
    if (options.form) {
      // Deliberately no Content-Type: the runtime sets it with the
      // multipart boundary, and overriding it produces a request the
      // server cannot parse.
      body = options.form;
    } else if (options.body !== undefined) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(options.body);
    }

    return this.fetchImpl(this.url(path, options.query), {
      method: options.method ?? "GET",
      headers,
      body,
      signal: options.signal,
    });
  }

  /** Make a request, refreshing once on a 401. */
  async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    let response = await this.send(
      path,
      options,
      options.anonymous ? null : await this.store.getAccessToken(),
    );

    if (response.status === 401 && !options.anonymous) {
      this.refreshing =
        this.refreshing ??
        this.refresh().finally(() => {
          this.refreshing = null;
        });

      if (await this.refreshing) {
        response = await this.send(
          path,
          options,
          await this.store.getAccessToken(),
        );
      }
      if (response.status === 401) this.onSignedOut?.();
    }

    if (!response.ok) {
      let detail: unknown;
      let message = `Request failed (${response.status})`;
      try {
        detail = await response.json();
        const d = (detail as { detail?: unknown })?.detail;
        if (typeof d === "string") message = d;
      } catch {
        // A non-JSON error body: keep the status-based message.
      }
      throw new ApiError(response.status, message, detail);
    }

    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  }

  /** Exchange the refresh token for a new pair. Returns false when the
   *  session is gone, having cleared it. */
  async refresh(): Promise<boolean> {
    const refreshToken = await this.store.getRefreshToken();
    if (!refreshToken) return false;
    try {
      const next = await this.request<{
        access_token: string;
        refresh_token: string;
      }>("/api/auth/refresh", {
        method: "POST",
        body: { refresh_token: refreshToken },
        // Anonymous: this request must not itself trigger a refresh.
        anonymous: true,
      });
      await this.store.setTokens({
        access: next.access_token,
        refresh: next.refresh_token,
      });
      return true;
    } catch {
      await this.store.clear();
      return false;
    }
  }

  get<T>(path: string, options: Omit<RequestOptions, "method" | "body"> = {}) {
    return this.request<T>(path, { ...options, method: "GET" });
  }

  post<T>(path: string, body?: unknown, options: RequestOptions = {}) {
    return this.request<T>(path, { ...options, method: "POST", body });
  }

  patch<T>(path: string, body?: unknown, options: RequestOptions = {}) {
    return this.request<T>(path, { ...options, method: "PATCH", body });
  }

  put<T>(path: string, body?: unknown, options: RequestOptions = {}) {
    return this.request<T>(path, { ...options, method: "PUT", body });
  }

  delete<T>(path: string, options: RequestOptions = {}) {
    return this.request<T>(path, { ...options, method: "DELETE" });
  }
}
