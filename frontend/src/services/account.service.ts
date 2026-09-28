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
  /** Hasn't agreed to the current privacy policy version yet. */
  privacy_consent_needed: boolean;
}

export interface DeletionPet {
  id: string;
  name: string;
  /** In `transferred`: who becomes the owner. */
  new_owner?: string | null;
  /** In `left`: whose pet it is. */
  owner?: string | null;
}

/** What deleting the account would do, for the confirmation screen. */
export interface DeletionPreview {
  /** False for the admin: that account can't be deleted. */
  can_delete: boolean;
  /** Nobody else looks after them: deleted with every record. */
  deleted: DeletionPet[];
  /** Shared with someone: they go to the first of those people. */
  transferred: DeletionPet[];
  /** Other people's pets: access ends. */
  left: DeletionPet[];
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

  async deletionPreview(): Promise<DeletionPreview> {
    const response = await api.get<DeletionPreview>('/me/account/deletion');
    return response.data;
  },

  /** For good. The server clears the session cookies. */
  async deleteAccount(password: string): Promise<void> {
    await api.delete('/me/account', { data: { password } });
  },

  async changePassword(currentPassword: string, newPassword: string): Promise<void> {
    await api.put('/me/password', { current_password: currentPassword, new_password: newPassword });
  },
};
