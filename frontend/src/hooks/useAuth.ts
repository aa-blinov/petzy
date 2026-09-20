import { useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { authService } from '../services/auth.service';
import { clearApiCaches, clearLocalAuthState, resetSessionExpired } from '../services/api';
import { SESSION_QUERY_KEY, useSession } from './useSession';
import type { LoginRequest } from '../services/auth.service';

const USERNAME_STORAGE_KEY = 'petzy:auth:username';

function readStoredUsername(): string | null {
  try {
    return localStorage.getItem(USERNAME_STORAGE_KEY);
  } catch {
    return null;
  }
}

function writeStoredUsername(value: string | null) {
  try {
    if (value) localStorage.setItem(USERNAME_STORAGE_KEY, value);
    else localStorage.removeItem(USERNAME_STORAGE_KEY);
  } catch {
    /* localStorage may be unavailable (private mode, SSR) — ignore */
  }
}

export function useAuth() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  // Auth state comes from the dedicated /auth/session probe, not from
  // a second observer on the ['pets'] data query. That second observer
  // was the reason a failed pet fetch read as a logout, and the reason
  // the login page kept firing authenticated requests.
  const { isAuthenticated, isLoginPage, username: sessionUsername } = useSession();

  // Prefer the server's answer; fall back to the last known name so
  // components that only display it (HistoryItem) don't blank out
  // during the first probe.
  const username = sessionUsername ?? readStoredUsername();

  const login = async (credentials: LoginRequest) => {
    try {
      const response = await authService.login(credentials);
      // Tokens are now in httpOnly cookies.
      writeStoredUsername(credentials.username);
      // A previous expiry latched the interceptor's sign-out guard.
      // Release it now that we hold fresh cookies, otherwise the next
      // genuine expiry would be swallowed.
      resetSessionExpired();
      // Drop everything the previous user cached, including the 401
      // that the session probe may be holding, so the protected pages
      // mount against an empty cache instead of a stale error.
      queryClient.clear();
      // Resolve the session probe here, while the submit button still
      // shows its own "Вход..." state, rather than after navigating.
      // Otherwise the protected page mounts with the session unknown
      // and ProtectedRoute covers the screen with the fullscreen
      // loader for one round trip — a flash between the login form and
      // the dashboard.
      //
      // A failure here is deliberately swallowed: the credentials were
      // accepted, so the user should land on the app and let it report
      // any connectivity problem, not be told their login failed.
      try {
        await queryClient.fetchQuery({
          queryKey: SESSION_QUERY_KEY,
          queryFn: () => authService.getSession(),
        });
      } catch {
        /* the protected route will probe again and surface the error */
      }
      return response;
    } catch (error) {
      writeStoredUsername(null);
      throw error;
    }
  };

  const logout = async () => {
    try {
      // Tell the backend to revoke the refresh_token and clear the
      // httpOnly cookies. Must happen before we clear local state —
      // if the request fails (network, server down) we still want
      // the user to land on /login so the local session is gone.
      await authService.logout();
    } catch (error) {
      // Don't block the user on a backend hiccup — the local
      // queryClient + storage cleanup below is what really matters
      // for the UI. The next protected request will 401 if the
      // backend is genuinely broken, and the session handler in
      // api.ts will sign the user out then too.
      console.warn('[auth] logout backend call failed, continuing with local cleanup', error);
    }
    // Clear the username AND the selected pet — the same list the
    // interceptor's sign-out path clears. Leaving the pet behind meant
    // the next user on this device booted pointed at the previous
    // user's pet.
    clearLocalAuthState();
    // React Query's cache is not the only copy — the service worker
    // holds one per /api/* response too.
    clearApiCaches();
    // Replace, not push, so the back button doesn't return to the
    // protected page after logout. Navigate BEFORE clearing so the
    // protected pages unmount first — clearing the cache while their
    // queries are still mounted makes every one of them refetch.
    navigate('/login', { replace: true });
    // Drop every cached query — pets, history, medications, session,
    // dashboard widgets. They belong to the user we just signed out
    // and could leak data if reused after a re-login as someone else.
    queryClient.clear();
  };

  return {
    /** true | false | undefined ("not known yet") */
    isAuthenticated,
    isLoading: !isLoginPage && isAuthenticated === undefined,
    username,
    login,
    logout,
  };
}
