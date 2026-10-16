import api from './api';

/** The areas a personal access token can hold: the ones web/security.py accepts. */
export const TOKEN_SCOPES = ['pets:read', 'events:write', 'history:read', 'medical:read'] as const;
export type TokenScope = (typeof TOKEN_SCOPES)[number];

/** What each area lets a token do, as the form and the list say it. */
export const SCOPE_LABELS: Record<TokenScope, string> = {
  'pets:read': 'Читать питомцев',
  'events:write': 'Записывать события',
  'history:read': 'Читать ленту и историю',
  'medical:read': 'Читать медкарту',
};

/** The lengths a token can be made for, in days (web/personal_tokens.py takes 1 to 365). */
export const TOKEN_DAYS = [30, 90, 365] as const;

export interface PersonalToken {
  id: string;
  name: string;
  scopes: TokenScope[];
  /** The first characters of the token: the way to tell it apart in the list. */
  prefix: string;
  created_at: string;
  expires_at: string;
  /** Empty until the token is used for the first time. */
  last_used_at: string | null;
  revoked_at: string | null;
}

export interface CreatedToken {
  id: string;
  name: string;
  scopes: TokenScope[];
  expires_at: string;
  prefix: string;
  /** The secret: shown once, the server keeps only its hash. */
  token: string;
}

export const PERSONAL_TOKENS_KEY = ['personal-tokens'] as const;

export const personalTokenService = {
  async create(body: { name: string; scopes: TokenScope[]; expires_in_days: number }): Promise<CreatedToken> {
    const response = await api.post<CreatedToken>('/me/tokens', body);
    return response.data;
  },
  async list(): Promise<PersonalToken[]> {
    const response = await api.get<{ tokens: PersonalToken[] }>('/me/tokens');
    return response.data.tokens;
  },
  async revoke(id: string): Promise<void> {
    await api.delete(`/me/tokens/${id}`);
  },
};

/** Whether a token still opens the API: not revoked, and not yet at its end. */
export const isWorking = (token: PersonalToken, now: number = Date.now()): boolean =>
  token.revoked_at === null && new Date(token.expires_at).getTime() > now;

/** A moment as the Russian reader writes it: 05.10.2026, 18:16. */
export const formatTokenTime = (iso: string): string =>
  new Date(iso).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
