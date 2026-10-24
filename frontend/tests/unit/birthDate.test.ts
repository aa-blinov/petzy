import { describe, expect, it } from 'vitest';
import { notInFuture, FUTURE_DATE_MESSAGE } from '../../src/utils/birthDate';

describe('notInFuture', () => {
  it('accepts an empty date: the birthday is optional', () => {
    expect(notInFuture('', '2026-03-05')).toBe(true);
    expect(notInFuture(undefined, '2026-03-05')).toBe(true);
  });

  it('accepts today and the past', () => {
    expect(notInFuture('2026-03-05', '2026-03-05')).toBe(true);
    expect(notInFuture('2020-01-01', '2026-03-05')).toBe(true);
  });

  it('refuses tomorrow', () => {
    expect(notInFuture('2026-03-06', '2026-03-05')).toBe(false);
  });

  it('says it in the one sentence every form uses', () => {
    expect(FUTURE_DATE_MESSAGE).toBe('Дата не может быть в будущем');
  });
});
