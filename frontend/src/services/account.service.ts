import api from './api';

export interface Account {
  username: string;
  full_name: string;
  /** Confirmed: password reset links go here. */
  email: string;
  email_verified: boolean;
  /** Typed in, waiting for its confirmation link. */
  pending_email: string;
  mail_enabled: boolean;
}

export const ACCOUNT_QUERY_KEY = ['account'] as const;

export const accountService = {
  async get(): Promise<Account> {
    const response = await api.get<Account>('/me/account');
    return response.data;
  },

  /** An empty email removes it. Needs the current password. */
  async changeEmail(email: string, password: string): Promise<Account> {
    const response = await api.put<Account>('/me/email', { email, password });
    return response.data;
  },

  async resendVerification(): Promise<void> {
    await api.post('/me/email/resend');
  },

  async changePassword(currentPassword: string, newPassword: string): Promise<void> {
    await api.put('/me/password', { current_password: currentPassword, new_password: newPassword });
  },
};
