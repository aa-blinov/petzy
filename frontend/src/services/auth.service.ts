import api from './api';

export interface LoginRequest {
  username: string;
  password: string;
}

/** The tokens themselves come only as httpOnly cookies. */
export interface LoginResponse {
  message: string;
}

export interface RefreshRequest {
  refresh_token: string;
}

export interface RefreshResponse {
  message: string;
  access_token: string;
}

export interface SessionResponse {
  username: string;
  is_admin: boolean;
}

export interface RegisterRequest {
  username: string;
  password: string;
  full_name?: string;
}

export const authService = {
  /** Creates the account; the session cookies come with the answer. */
  async register(data: RegisterRequest): Promise<void> {
    await api.post('/auth/register', data);
  },

  async registrationOpen(): Promise<boolean> {
    const response = await api.get<{ open: boolean }>('/auth/registration');
    return response.data.open;
  },

  async login(credentials: LoginRequest): Promise<LoginResponse> {
    const response = await api.post<LoginResponse>('/auth/login', credentials);
    return response.data;
  },

  async getSession(): Promise<SessionResponse> {
    // The app's auth probe. Returns 200 with the signed-in identity, or
    // 401 when the cookies are dead — and 401 is the only answer that
    // means "signed out".
    const response = await api.get<SessionResponse>('/auth/session');
    return response.data;
  },

  async refresh(refreshToken: string): Promise<RefreshResponse> {
    const response = await api.post<RefreshResponse>('/auth/refresh', { refresh_token: refreshToken });
    return response.data;
  },

  async logout(): Promise<void> {
    // Tell the backend to invalidate the refresh_token row in
    // MongoDB and clear the httpOnly cookies. Without this call the
    // tokens remain valid until the TTL expires — a security issue
    // (stolen cookies stay usable after "logout") and a UX issue (a
    // re-login right after logout can re-use the old refresh_token).
    await api.post('/auth/logout');
  }
};

