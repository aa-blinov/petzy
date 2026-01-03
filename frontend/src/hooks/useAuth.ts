import { useState, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { authService } from '../services/auth.service';
import { petsService } from '../services/pets.service';
import type { LoginRequest } from '../services/auth.service';

export function useAuth() {
  const [username, setUsername] = useState<string | null>(null);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const location = useLocation();

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
      // Invalidate pets query to refetch with new auth
      queryClient.invalidateQueries({ queryKey: ['pets'] });
      return response;
    } catch (error: any) {
      setUsername(null);
      throw error;
    }
  };

  const logout = async () => {
    try {
      await authService.logout();
      setUsername(null);
      // Clear all queries on logout
      queryClient.clear();
      navigate('/login');
    } catch (error) {
      console.error('Logout error:', error);
    }
  };

  return {
    isAuthenticated,
    isLoading,
    username,
    login,
    logout
  };
}

