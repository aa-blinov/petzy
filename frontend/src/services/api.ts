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

// Tracks whether we've already kicked off a forced redirect for the
// current auth failure — multiple parallel 401s shouldn't each trigger
// their own /login navigation.
let forcedRedirect = false;
function forceLogoutAndRedirect(reason: string) {
  if (forcedRedirect) return;
  forcedRedirect = true;
  // Clear client-side state. Best-effort: even if queryClient is
  // unavailable (early boot), we still redirect.
  try {
    const w = window as any;
    w.localStorage?.removeItem('petzy:auth:username');
    w.localStorage?.removeItem('selectedPetId');
    w.localStorage?.removeItem('selectedPetName');
  } catch { /* ignore */ }
  try {
    // Send the user to /login. setTimeout(0) keeps the redirect out
    // of any in-flight render — avoids React complaining about
    // state updates during render.
    setTimeout(() => {
      if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
        window.location.replace('/login');
      }
      forcedRedirect = false;
    }, 0);
  } catch {
    forcedRedirect = false;
  }
  // eslint-disable-next-line no-console
  console.info(`[auth] ${reason} — redirecting to /login`);
}

// Response interceptor — handle 401 by attempting a silent refresh,
// then redirect to /login if refresh fails.
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = (error.config ?? {}) as InternalAxiosRequestConfig & { _retry?: boolean };

    // Handle 401 Unauthorized — try to refresh token.
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      const url = originalRequest.url || '';
      // Don't refresh on the auth endpoints themselves — they're
      // the source of the 401 in the first place.
      if (url.includes('/auth/login') || url.includes('/auth/refresh')) {
        // The login form or the refresh probe itself failed — send
        // the user back to /login (only if we're not already there).
        if (url.includes('/auth/refresh')) forceLogoutAndRedirect('refresh failed');
        return Promise.reject(error);
      }

      try {
        // Try to refresh token. The /auth/refresh endpoint sets
        // fresh httpOnly access_token + refresh_token cookies on
        // success.
        await axios.post(`${API_URL}/auth/refresh`, {}, { withCredentials: true });
        // Refresh succeeded — replay the original request with the
        // new credentials attached.
        return api(originalRequest);
      } catch (refreshError) {
        // Refresh failed: the refresh_token is gone (expired or
        // revoked). Force a logout + redirect instead of leaving the
        // user on a frozen screen that just shows a blank error.
        forceLogoutAndRedirect('refresh token invalid');
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

export default api;

