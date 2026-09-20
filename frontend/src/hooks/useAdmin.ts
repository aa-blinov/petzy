import { useSession } from './useSession';

/**
 * Admin flag for the current user.
 *
 * Derived from the session probe rather than its own
 * GET /auth/check-admin request. The separate request was a second
 * unguarded authenticated call on every page (login page included,
 * since BottomTabBar calls this hook before its `/login` early
 * return), and its `retry: 1` overrode the app-wide "never retry a
 * 401" rule — so every expiry produced a doubled 401 here.
 */
export function useAdmin() {
  const { isAdmin, isAuthenticated } = useSession();

  return {
    isAdmin,
    isLoading: isAuthenticated === undefined,
  };
}
