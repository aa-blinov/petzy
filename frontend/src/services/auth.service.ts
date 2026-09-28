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
  full_name: string;
  /** For password recovery; confirmed by a letter. Required while mail works. */
  email?: string;
  /** Consent to personal data processing (/consent); required. */
  privacy_consent: boolean;
}

export interface RegistrationStatus {
  open: boolean;
  /** Letters can be sent: recovery by email works. */
  mail_enabled: boolean;
}

export const authService = {
  /** Creates the account; the session cookies come with the answer. */
  async register(data: RegisterRequest): Promise<void> {
    await api.post('/auth/register', data);
  },

  async registrationStatus(): Promise<RegistrationStatus> {
    const response = await api.get<RegistrationStatus>('/auth/registration');
    return response.data;
  },

  /** Always the same answer, whether or not the account exists. */
  async forgotPassword(login: string): Promise<string> {
    const response = await api.post<{ message: string }>('/auth/password/forgot', { login });
    return response.data.message;
  },

  /** Sets the new password and signs in; returns the account's login. */
  async resetPassword(token: string, password: string): Promise<string> {
    const response = await api.post<{ username: string }>('/auth/password/reset', { token, password });
    return response.data.username;
  },

  async verifyEmail(token: string): Promise<void> {
    await api.post('/auth/email/verify', { token });
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

