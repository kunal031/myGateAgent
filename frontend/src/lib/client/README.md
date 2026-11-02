# The API client

One client, two platforms. Everything here is free of `window`,
`document` and `localStorage`, so React Native can import it unchanged.

```
transport.ts    ApiClient: URLs, auth header, 401 refresh+retry, errors
storage.ts      TokenStore interface + MemoryTokenStore
web-storage.ts  WebTokenStore (localStorage)
web.ts          the single instance the Next.js app shares
```

## Using it from React Native

Only the storage adapter and the construction differ:

```ts
import AsyncStorage from "@react-native-async-storage/async-storage";
import { ApiClient, type TokenStore } from "@/lib/client";

class NativeTokenStore implements TokenStore {
  async getAccessToken() { return AsyncStorage.getItem("gm.access"); }
  async getRefreshToken() { return AsyncStorage.getItem("gm.refresh"); }
  async setTokens({ access, refresh }: { access: string; refresh: string }) {
    await AsyncStorage.multiSet([["gm.access", access], ["gm.refresh", refresh]]);
  }
  async clear() { await AsyncStorage.multiRemove(["gm.access", "gm.refresh"]); }
}

export const api = new ApiClient({
  baseUrl: Config.API_URL,
  store: new NativeTokenStore(),
  onSignedOut: () => navigation.replace("SignIn"),
});
```

Prefer `expo-secure-store` over AsyncStorage for the refresh token: it is
backed by the Android Keystore, so the token is not readable from a
plain filesystem dump of a rooted device.

The endpoint functions in `lib/api.ts`, `lib/tags.ts` and `lib/papers.ts`
import the *web* instance, so a native app either passes its own client
or re-exports these against its own. Splitting them into a shared
package is the next step if a second app appears.

## Why not patch fetch

The previous design reassigned `window.fetch` once at startup. With 48
call sites and no shared wrapper that was a reasonable trade, but it
cannot move to React Native, it makes the token flow invisible at the
call site, and it is untestable without a DOM. `ApiClient` takes
`fetchImpl` instead, so a test passes a stub and asserts on what was
sent.

## Single-flight refresh

Concurrent 401s share one refresh promise. This is not an optimisation.
The server rotates refresh tokens and treats a replayed one as theft, so
two parallel refreshes would present the same token, the second would be
seen as a reuse, and **every session on the account would be revoked**.
The shared promise is what stops the client reporting itself stolen.

## Adding httpOnly cookies later

`TokenStore` is the seam. A `CookieTokenStore` returns `null` for the
refresh token and lets the browser send it automatically; `ApiClient`
needs a `credentials: "include"` option and nothing else changes. Web
would get XSS-proof refresh tokens while Android keeps the header path.
