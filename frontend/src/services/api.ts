import axios, { AxiosError } from 'axios';
import type { InternalAxiosRequestConfig } from 'axios';

const API_URL = import.meta.env.VITE_API_URL || '/api';

// Create axios instance
const api = axios.create({
  baseURL: API_URL,
  withCredentials: true, // Important for httpOnly cookies
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor - add auth token if needed
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // Tokens are in httpOnly cookies, so we don't need to add them manually
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor - handle errors and token refresh
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    // Handle 401 Unauthorized - try to refresh token
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      // Don't try to refresh if we're already on the login or refresh endpoint
      const url = originalRequest.url || '';
      if (url.includes('/auth/login') || url.includes('/auth/refresh')) {
        return Promise.reject(error);
      }

      try {
        // Try to refresh token
        await axios.post(`${API_URL}/auth/refresh`, {}, { withCredentials: true });
        // Retry original request
        return api(originalRequest);
      } catch (refreshError) {
        // Refresh failed - don't redirect here, let the component handle it
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

export default api;

