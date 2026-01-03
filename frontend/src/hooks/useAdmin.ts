import { useQuery } from '@tanstack/react-query';
import api from '../services/api';

interface AdminStatusResponse {
  is_admin: boolean;
}

export function useAdmin() {
  // Check admin status only once per session (until cache is cleared)
  const { data, isLoading } = useQuery({
    queryKey: ['admin-status'],
    queryFn: async () => {
      const response = await api.get<AdminStatusResponse>('/auth/check-admin');
      return response.data.is_admin === true;
    },
    staleTime: Infinity, // Never consider stale - valid for entire session
    gcTime: Infinity, // Keep in cache forever (until logout clears it)
    refetchOnMount: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    retry: 1,
  });

  return { 
    isAdmin: data ?? false, 
    isLoading 
  };
}

