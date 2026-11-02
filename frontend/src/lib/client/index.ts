/**
 * The client this app uses, and the pieces another platform needs.
 *
 * A React Native app imports ApiClient and the endpoint modules from
 * here and constructs its own instance with its own TokenStore:
 *
 *   const api = new ApiClient({
 *     baseUrl: Config.API_URL,
 *     store: new SecureStoreTokenStore(),
 *     onSignedOut: () => navigation.replace("SignIn"),
 *   });
 *
 * Nothing below this line touches `window`, `document` or localStorage,
 * which is what makes that possible.
 */

export { ApiClient, ApiError } from "./transport";
export type { ApiClientOptions, FetchLike, RequestOptions } from "./transport";
export { MemoryTokenStore } from "./storage";
export type { TokenStore } from "./storage";
export { WebTokenStore } from "./web-storage";
