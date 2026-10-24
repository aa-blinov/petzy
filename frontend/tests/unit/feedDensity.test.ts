import { describe, expect, it } from 'vitest';
import { seenLongEnough } from '../../src/utils/feedDensity';

describe('seenLongEnough', () => {
  const now = new Date(2026, 9, 24, 15, 30);
  it('keeps the full card for the first week', () => {
    expect(seenLongEnough('2026-10-24', now)).toBe(false);
    expect(seenLongEnough('2026-10-18', now)).toBe(false);
  });
  it('turns to one line on the seventh day', () => {
    expect(seenLongEnough('2026-10-17', now)).toBe(true);
    expect(seenLongEnough('2026-01-01', now)).toBe(true);
  });
  it('keeps the full card when the date is missing or unreadable', () => {
    expect(seenLongEnough(null, now)).toBe(false);
    expect(seenLongEnough('вчера', now)).toBe(false);
  });
});
