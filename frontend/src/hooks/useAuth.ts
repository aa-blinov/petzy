import { useState, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { authService } from '../services/auth.service';
import { petsService } from '../services/pets.service';
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
  // Username is shared between all components via localStorage. The
  // tokens live in HttpOnly cookies so JS can't read them, but the
  // human-readable username is fine in localStorage and lets every
  // useAuth() instance see the same value without prop-drilling.
  const [username, setUsernameState] = useState<string | null>(() => readStoredUsername());
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const location = useLocation();

  const setUsername = (value: string | null) => {
    writeStoredUsername(value);
    setUsernameState(value);
  };

  // Check if we're on the login page using React Router location
  const isLoginPage = useMemo(() => {
    return location.pathname === '/login' || location.pathname.endsWith('/login');
  }, [location.pathname]);

  // Use React Query to check auth - this will be shared with other components using pets
  // React Query automatically deduplicates requests with the same queryKey
  // Use refetchOnMount: false to prevent refetching if data is already in cache
  const { isLoading: isPetsLoading, isError, error } = useQuery({
    queryKey: ['pets'],
    queryFn: () => petsService.getPets(),
    enabled: !isLoginPage, // Skip if on login page
    retry: (failureCount, error: any) => {
      // Don't retry on 401 (unauthorized)
      if (error?.response?.status === 401) {
        return false;
      }
      return failureCount < 1; // Retry once for other errors
    },
    staleTime: 30 * 1000, // Consider data fresh for 30 seconds (matches App.tsx default)
    gcTime: 5 * 60 * 1000, // Keep in cache for 5 minutes
    refetchOnMount: false, // Don't refetch if data is already in cache
    refetchOnWindowFocus: false, // Already set in App.tsx, but explicit here
  });

  // Determine auth state from pets query
  // If query is loading or errored with 401, user is not authenticated
  const is401Error = useMemo(() => {
    return error && (error as any)?.response?.status === 401;
  }, [error]);

  const isAuthenticated = useMemo(() => {
    return !isLoginPage && !is401Error && !isPetsLoading && !isError;
  }, [isLoginPage, is401Error, isPetsLoading, isError]);

  const isLoading = !isLoginPage && isPetsLoading;

  const login = async (credentials: LoginRequest) => {
    try {
      const response = await authService.login(credentials);
      // After successful login, tokens are set in httpOnly cookies
      setUsername(credentials.username);
      // Invalidate all auth-related queries to refetch with new user context
      queryClient.invalidateQueries({ queryKey: ['pets'] });
      queryClient.invalidateQueries({ queryKey: ['admin-status'] });
      return response;
    } catch (error: any) {
      setUsername(null);
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
      // for the UI. The next page load will fail with 401 if the
      // backend is genuinely broken, and the 401-handler in api.ts
      // will redirect to /login then too.
      console.warn('[auth] logout backend call failed, continuing with local cleanup', error);
    }
    setUsername(null);
    // Drop every cached query — pets, history, medications, admin
    // status, dashboard widgets. They belong to the user we just
    // signed out and could leak data if reused after a re-login as
    // someone else.
    queryClient.clear();
    // Replace, not push, so the back button doesn't return to the
    // protected page after logout.
    navigate('/login', { replace: true });
  };

  return {
    isAuthenticated,
    isLoading,
    username,
    login,
    logout
  };
}

