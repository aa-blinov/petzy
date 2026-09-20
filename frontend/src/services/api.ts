import axios, { AxiosError } from 'axios';
import type { InternalAxiosRequestConfig } from 'axios';

// Base URL for API requests.
// Use relative path by default to work with proxy/Nginx.
let API_URL = import.meta.env.VITE_API_URL || '/api';

// Safeguard: if API_URL is hardcoded to localhost:3000 but we are on a real domain,
// force it to be relative '/api'
if (API_URL.includes('localhost:3000') && !window.location.href.includes('localhost:3000')) {
  API_URL = '/api';
}

// Create axios instance
const api = axios.create({
  baseURL: API_URL,
  withCredentials: true,
});

// Request interceptor — tokens are in httpOnly cookies so we don't
// need to add an Authorization header manually.
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => config,
  (error) => Promise.reject(error),
);

/**
 * HTTP status behind a rejected request, or undefined for a failure
 * that never reached the server (network error, cancellation).
 *
 * Callers need this to tell "the session is gone" (401) from "the
 * request failed for some other reason" — the distinction the old
 * auth state was missing.
 */
export function httpStatus(error: unknown): number | undefined {
  return axios.isAxiosError(error) ? error.response?.status : undefined;
}

// ---------------------------------------------------------------------------
// Session expiry
//
// There is exactly ONE way the app leaves a protected page when auth
// fails: the handler registered below by <SessionExpiryBridge>, which
// performs a React Router navigation.
//
// This file previously ALSO called window.location.replace('/login'),
// so a single 401 raced a soft router redirect against a full document
// reload. Which one won came down to network timing, and when both
// landed the user watched the login screen appear, then the entire SPA
// reboot and show it again — the flicker. Keep window.location
// navigation out of this module.
// ---------------------------------------------------------------------------

type SessionExpiredHandler = () => void;

let sessionExpiredHandler: SessionExpiredHandler | null = null;

/** Register the app's single sign-out path. Pass null to unregister. */
export function setSessionExpiredHandler(handler: SessionExpiredHandler | null) {
  sessionExpiredHandler = handler;
}

// Latched while a session failure is being handled so a burst of
// parallel 401s (the dashboard fires session + pets + medications +
// upcoming doses at once) collapses into one sign-out.
//
// The old guard reset itself synchronously right after kicking off the
// redirect. window.location.replace() navigates asynchronously, so the
// flag was already free again while the old document was still alive
// and every remaining 401 fired another redirect on top of the pending
// one. This latch is released only by resetSessionExpired(), on a
// successful login.
let sessionExpired = false;

/** Release the latch once fresh credentials are in hand. */
export function resetSessionExpired() {
  sessionExpired = false;
}

/**
 * Wipe every piece of the signed-in user's identity we keep outside
 * httpOnly cookies.
 *
 * Exported so the explicit logout path uses the same list: clearing
 * only the username left `selectedPetId`/`selectedPetName` behind, and
 * the next user to sign in on that device started out pointed at the
 * previous user's pet — a burst of 403s plus their pet's name in the
 * navbar until usePet's recovery effect noticed and switched.
 */
export function clearLocalAuthState() {
  try {
    localStorage.removeItem('petzy:auth:username');
    localStorage.removeItem('selectedPetId');
    localStorage.removeItem('selectedPetName');
  } catch {
    /* localStorage may be unavailable (private mode) — ignore */
  }
}

/**
 * Drop the service worker's API response caches.
 *
 * queryClient.clear() only empties React Query's in-memory cache; the
 * SW keeps its own copy of every /api/* response it has seen. Without
 * this, signing out left the previous user's responses on disk, ready
 * to be served to whoever signs in next on the same device — and to
 * show up briefly before the network answer replaced them.
 *
 * Fire-and-forget: a failure here must never block signing out.
 */
export function clearApiCaches(): void {
  if (typeof caches === 'undefined') return;
  caches
    .keys()
    .then((keys) => Promise.all(keys.filter((k) => k.startsWith('api-')).map((k) => caches.delete(k))))
    .catch(() => {
      /* Cache Storage unavailable or blocked — nothing to clean up */
    });
}

function handleSessionExpired(reason: string) {
  if (sessionExpired) return;
  sessionExpired = true;
  clearLocalAuthState();
  clearApiCaches();
  console.info(`[auth] ${reason} — signing out`);

  if (sessionExpiredHandler) {
    sessionExpiredHandler();
    return;
  }

  // No handler means React hasn't mounted yet, so nothing can navigate
  // on our behalf. A hard redirect is the only option left, and it
  // cannot race the router because the router doesn't exist yet.
  if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
    window.location.replace('/login');
  }
}

// In-flight refresh, shared by every 401 that arrives while it runs.
// Without this, N parallel 401s fired N POST /auth/refresh requests and
// N sign-out attempts.
let refreshInFlight: Promise<void> | null = null;

function refreshSession(): Promise<void> {
  if (!refreshInFlight) {
    // Deliberately plain axios, not `api`: the refresh call must not
    // re-enter this interceptor.
    refreshInFlight = axios
      .post(`${API_URL}/auth/refresh`, {}, { withCredentials: true })
      .then(() => undefined)
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

// Response interceptor — handle 401 by attempting a silent refresh,
// then sign out if the refresh fails.
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = (error.config ?? {}) as InternalAxiosRequestConfig & { _retry?: boolean };

    if (error.response?.status !== 401 || originalRequest._retry) {
      return Promise.reject(error);
    }

    const url = originalRequest.url || '';

    // A 401 from the login form means "wrong password". It belongs to
    // the form, not to the session machinery.
    if (url.includes('/auth/login')) {
      return Promise.reject(error);
    }

    // The refresh probe itself is unauthorised — nothing left to try.
    if (url.includes('/auth/refresh')) {
      handleSessionExpired('refresh rejected');
      return Promise.reject(error);
    }

    // Already signing out; let useAuth.logout() finish its own cleanup
    // rather than triggering a second, competing sign-out here.
    if (url.includes('/auth/logout')) {
      return Promise.reject(error);
    }

    originalRequest._retry = true;

    try {
      await refreshSession();
    } catch {
      handleSessionExpired('refresh token invalid');
      // Reject with the ORIGINAL 401, not the refresh error, so callers
      // (useSession in particular) can tell "session is gone" from
      // "request failed for some other reason".
      return Promise.reject(error);
    }

    // Refresh succeeded — replay the original request with the new
    // credentials attached.
    return api(originalRequest);
  },
);

export default api;
