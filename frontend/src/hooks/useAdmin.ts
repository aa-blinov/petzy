import { useState, useEffect } from 'react';
import api from '../services/api';

interface AdminStatusResponse {
  is_admin: boolean;
}

export function useAdmin() {
  const [isAdmin, setIsAdmin] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    const checkAdmin = async () => {
      try {
        const response = await api.get<AdminStatusResponse>('/auth/check-admin');
        setIsAdmin(response.data.is_admin === true);
      } catch (error) {
        console.error('Error checking admin status:', error);
        setIsAdmin(false);
      } finally {
        setIsLoading(false);
      }
    };

    checkAdmin();
  }, []);

  return { isAdmin, isLoading };
}

