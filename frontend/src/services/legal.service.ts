import api from './api';

/** The policy's facts only the operator knows (server env; empty until set). */
export interface LegalInfo {
  policy_version: string;
  operator: string;
  contact_email: string;
  server_location: string;
  backups_kept_days: number;
}

export const LEGAL_QUERY_KEY = ['legal'] as const;

export const legalService = {
  async get(): Promise<LegalInfo> {
    const response = await api.get<LegalInfo>('/legal');
    return response.data;
  },

  /** Agree to the policy version the page showed. */
  async acceptPrivacyPolicy(version: string): Promise<void> {
    await api.post('/me/privacy-consent', { version });
  },
};
