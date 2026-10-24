import { describe, expect, it } from 'vitest';
import { shareInviteFailure, shareLoginProblem, sharePeople } from '../../src/utils/petShare';

describe('sharePeople', () => {
  it('lists members first, then the invited, each once', () => {
    expect(sharePeople({ shared_with: ['anna'], share_invites: ['boris', 'anna'] })).toEqual([
      { username: 'anna', status: 'member' },
      { username: 'boris', status: 'invited' },
    ]);
  });
  it('is empty for a pet nobody reaches', () => {
    expect(sharePeople({})).toEqual([]);
  });
});

describe('shareLoginProblem', () => {
  const people = sharePeople({ shared_with: ['anna'], share_invites: ['boris'] });
  it('asks for a login', () => {
    expect(shareLoginProblem('  ', 'me', people)).toBe('Введите логин человека');
  });
  it('refuses the own login, without regard to case', () => {
    expect(shareLoginProblem('ME', 'me', people)).toBe('Это ваш логин');
  });
  it('says who already has the access and who is already invited', () => {
    expect(shareLoginProblem('Anna', 'me', people)).toBe('У anna уже есть доступ');
    expect(shareLoginProblem('boris', 'me', people)).toBe('boris уже приглашён');
  });
  it('lets a new login go', () => {
    expect(shareLoginProblem('clara', 'me', people)).toBeNull();
  });
});

describe('shareInviteFailure', () => {
  it('names the person for the two harmless refusals', () => {
    expect(shareInviteFailure('anna', 'validation_error_already_shared', '')).toBe('У anna уже есть доступ');
    expect(shareInviteFailure('anna', 'share_already_invited', '')).toBe('anna уже приглашён');
  });
  it('keeps what the server said for any other refusal', () => {
    expect(shareInviteFailure('anna', undefined, 'Пользователь отключён')).toBe('Приглашение для anna не отправилось: Пользователь отключён');
    expect(shareInviteFailure('anna', undefined, '')).toBe('Приглашение для anna не отправилось');
  });
});
