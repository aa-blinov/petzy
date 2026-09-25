import type { FieldErrors } from 'react-hook-form';
import { announce } from './announce';
import { pluralRu } from './relativeTime';

function countErrors(errors: FieldErrors): number {
  let n = 0;
  for (const value of Object.values(errors)) {
    if (!value) continue;
    if (typeof value === 'object' && 'message' in value && value.message) n += 1;
    else if (typeof value === 'object') n += countErrors(value as FieldErrors);
  }
  return n;
}

/**
 * `handleSubmit(onSubmit, onInvalidSubmit)`: a save that failed
 * validation used to do nothing visible. Now the first message is
 * scrolled into view, its field takes focus, and a screen reader hears
 * how many fields need fixing.
 */
export function onInvalidSubmit(errors: FieldErrors) {
  const count = Math.max(1, countErrors(errors));
  announce(
    count === 1 ? 'Исправьте поле с ошибкой' : `Исправьте ${count} ${pluralRu(count, 'поле', 'поля', 'полей')} с ошибками`,
    'assertive',
  );
  // The messages render on the next commit.
  requestAnimationFrame(() => {
    const first = document.querySelector('.field-error');
    const item = first?.closest('.adm-form-item') ?? first;
    if (!item) return;
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    item.scrollIntoView({ block: 'center', behavior: reduce ? 'auto' : 'smooth' });
    const control = item.matches('[role="button"]')
      ? (item as HTMLElement)
      : item.querySelector<HTMLElement>('input:not([type="hidden"]):not([readonly]), textarea:not([readonly]), button, [role="button"]');
    control?.focus({ preventScroll: true });
  });
}
