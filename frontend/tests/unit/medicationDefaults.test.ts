import { describe, expect, it } from 'vitest';
import { ALL_WEEKDAYS, newCourseDefaults } from '../../src/utils/medicationDefaults';

describe('newCourseDefaults', () => {
  it('gives the course every day of the week, so a daily course needs no taps', () => {
    expect(newCourseDefaults('2026-03-05').days).toEqual([0, 1, 2, 3, 4, 5, 6]);
  });

  it('begins the course today', () => {
    expect(newCourseDefaults('2026-03-05').started_on).toBe('2026-03-05');
  });

  it('hands out a copy, so changing the chosen days never changes the constant', () => {
    const days = newCourseDefaults('2026-03-05').days;
    days.pop();
    expect(ALL_WEEKDAYS).toHaveLength(7);
  });
});
