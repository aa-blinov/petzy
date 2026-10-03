import type { KeyboardEvent } from 'react';

/**
 * The keys of a radio group (WAI-ARIA): one stop in the Tab order, the arrows move inside it and choose as they go. Without
 * it each of dozens of options is a Tab stop and the Save button is a hundred presses away.
 */
export function rovingKeyDown(e: KeyboardEvent<HTMLElement>): void {
  const forward = e.key === 'ArrowRight' || e.key === 'ArrowDown';
  const back = e.key === 'ArrowLeft' || e.key === 'ArrowUp';
  if (!forward && !back && e.key !== 'Home' && e.key !== 'End') return;
  const radios = [...e.currentTarget.querySelectorAll<HTMLElement>('[role="radio"]')];
  const at = radios.indexOf(document.activeElement as HTMLElement);
  if (at < 0) return;
  const next = e.key === 'Home' ? 0 : e.key === 'End' ? radios.length - 1 : (at + (forward ? 1 : -1) + radios.length) % radios.length;
  e.preventDefault();
  radios[next].focus();
  radios[next].click();
}

/** The one radio of a group that is a Tab stop: the chosen one, or the first when none of them is. */
export const rovingTabIndex = (on: boolean, first: boolean, anyOn: boolean): 0 | -1 => (on || (!anyOn && first) ? 0 : -1);
