import type { Pet } from '../services/pets.service';

export type ShareStatus = 'member' | 'invited';

export interface SharePerson {
  username: string;
  status: ShareStatus;
}

/** The words next to a person: they have the access, or the invitation waits for their answer. */
export const SHARE_STATUS_LABEL: Record<ShareStatus, string> = {
  member: 'Есть доступ',
  invited: 'Приглашён',
};

/** Who the pet reaches, members first and then the invited, each once. */
export function sharePeople(pet: Pick<Pet, 'shared_with' | 'share_invites'>): SharePerson[] {
  const members = pet.shared_with ?? [];
  const invited = (pet.share_invites ?? []).filter((u) => !members.includes(u));
  return [
    ...members.map((username) => ({ username, status: 'member' as const })),
    ...invited.map((username) => ({ username, status: 'invited' as const })),
  ];
}

/** What is wrong with a login before it is sent, or null when it can go. Logins match without regard to case. */
export function shareLoginProblem(login: string, ownLogin: string | null, people: SharePerson[]): string | null {
  const typed = login.trim().toLowerCase();
  if (!typed) return 'Введите логин человека';
  if (ownLogin && typed === ownLogin.trim().toLowerCase()) return 'Это ваш логин';
  const known = people.find((p) => p.username.toLowerCase() === typed);
  if (known) return known.status === 'member' ? `У ${known.username} уже есть доступ` : `${known.username} уже приглашён`;
  return null;
}

/** What the server's refusal of one invitation is called, said by name: the same words the pet form used. */
export function shareInviteFailure(login: string, code: string | undefined, said: string): string {
  if (code === 'validation_error_already_shared') return `У ${login} уже есть доступ`;
  if (code === 'share_already_invited') return `${login} уже приглашён`;
  return `Приглашение для ${login} не отправилось${said ? `: ${said}` : ''}`;
}
