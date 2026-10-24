const pad = (n: number) => String(n).padStart(2, '0');

const toIso = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

/** «17082025» into «17.08.2025» as the digits come; anything but digits is dropped. */
export function formatTyped(raw: string): string {
  const digits = raw.replace(/\D/g, '').slice(0, 8);
  return [digits.slice(0, 2), digits.slice(2, 4), digits.slice(4)].filter(Boolean).join('.');
}

export interface TypedDateLimits {
  today: Date;
  yearsBack: number;
  yearsForward: number;
}

export type TypedDateResult = { iso: string; error: '' } | { iso: null; error: string };

export const INCOMPLETE_DATE = 'Введите дату полностью, например 17.08.2025';

/**
 * What a typed date amounts to: the date, or what is wrong with it. An unfinished text (`12.1`) is as much a
 * problem as a date that does not exist: the field must not look valid while the form still holds an older date.
 * Empty text is no problem, nothing was typed.
 */
export function readTypedDate(raw: string, { today, yearsBack, yearsForward }: TypedDateLimits): TypedDateResult {
  const text = formatTyped(raw);
  if (!text) return { iso: null, error: '' };
  if (text.length < 10) return { iso: null, error: INCOMPLETE_DATE };
  const [d, m, y] = text.split('.').map(Number);
  const date = new Date(y, m - 1, d);
  const real = date.getFullYear() === y && date.getMonth() === m - 1 && date.getDate() === d;
  if (!real) return { iso: null, error: 'Такой даты нет. Введите, например, 17.08.2025' };
  const thisYear = today.getFullYear();
  const iso = toIso(date);
  const todayIso = toIso(today);
  if (yearsForward === 0 && iso > todayIso) return { iso: null, error: 'Дата не может быть в будущем' };
  if (yearsBack === 0 && iso < todayIso) return { iso: null, error: 'Дата уже прошла' };
  if (y < thisYear - yearsBack) return { iso: null, error: `Год не раньше ${thisYear - yearsBack}` };
  if (y > thisYear + yearsForward) return { iso: null, error: `Год не позже ${thisYear + yearsForward}` };
  return { iso, error: '' };
}
