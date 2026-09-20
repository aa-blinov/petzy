import { useMemo } from 'react';
import { useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { authService } from '../services/auth.service';
import { httpStatus } from '../services/api';

export const SESSION_QUERY_KEY = ['session'] as const;

/**
 * Single source of truth for "is there a signed-in user?".
 *
 * Auth state used to be inferred from the ['pets'] query, which
 * conflated three unrelated things: a cold cache, a failed data fetch,
 * and a dead session. `isAuthenticated` was `!isError && !isLoading`,
 * so a 500 or a dropped connection on /api/pets bounced a perfectly
 * authenticated user to /login.
 *
 * Here the answer is a tri-state and only a 401 counts as signed out:
 *
 *   undefined — not known yet (first probe still in flight)
 *   true      — signed in
 *   false     — the server answered 401
 *
 * A transient failure keeps the previous answer, because React Query
 * holds `data` across a failed refetch. A network blip no longer looks
 * like a logout.
 */
export function useSession() {
  const location = useLocation();
  const isLoginPage = useMemo(
    () => location.pathname === '/login' || location.pathname.endsWith('/login'),
    [location.pathname],
  );

  const { data, error, isFetching, refetch } = useQuery({
    queryKey: SESSION_QUERY_KEY,
    queryFn: () => authService.getSession(),
    // The login page must not issue authenticated requests. Every
    // consumer of session state goes through this hook, so all
    // observers of the key agree on `enabled` — a single observer
    // without it would silently re-enable the query for everyone,
    // which is exactly how `enabled: !isLoginPage` on ['pets'] was
    // defeated by usePet() rendering inside the Navbar.
    enabled: !isLoginPage,
    // A 401 is a final answer, so don't hammer it. Anything else is
    // worth one more shot before we give up and show a retry.
    retry: (failureCount, err) => (httpStatus(err) === 401 ? false : failureCount < 1),
    staleTime: 5 * 60 * 1000,
    gcTime: Infinity,
    refetchOnMount: false,
    refetchOnWindowFocus: false,
  });

  const isUnauthorized = httpStatus(error) === 401;

  const isAuthenticated = useMemo<boolean | undefined>(() => {
    if (isLoginPage) return false;
    if (data) return true;
    if (isUnauthorized) return false;
    return undefined;
  }, [isLoginPage, data, isUnauthorized]);

  return {
    /** true | false | undefined ("not known yet") */
    isAuthenticated,
    isLoginPage,
    username: data?.username ?? null,
    isAdmin: data?.is_admin ?? false,
    isFetching,
    /** Set when the probe failed for a reason other than 401. */
    probeError: !data && !isUnauthorized && error ? error : null,
    retryProbe: refetch,
  };
}
