import { formatDate } from './dateUtils';

/** How far back a dose can be put: a week covers «отметил(а) позже» and
 *  a forgotten weekend without turning the picker into a calendar. */
const DAYS_BACK = 7;

export interface IntakeWhen {
  date: string; // YYYY-MM-DD
  time: string; // HH:MM
}

const pad = (n: number) => String(n).padStart(2, '0');

function dayLabel(day: Date, daysAgo: number): string {
  if (daysAgo === 0) return 'Сегодня';
  if (daysAgo === 1) return 'Вчера';
  return day.toLocaleDateString('ru-RU', { weekday: 'short', day: 'numeric', month: 'short' });
}

/** The last week, newest first, plus `keep` when it's older (a dose from
 *  a month ago opens on its own day, not on today). */
export function dayColumn(keep?: string) {
  const today = new Date();
  const days = Array.from({ length: DAYS_BACK }, (_, i) => {
    const day = new Date(today.getFullYear(), today.getMonth(), today.getDate() - i);
    return { label: dayLabel(day, i), value: formatDate(day) };
  });
  if (keep && !days.some((d) => d.value === keep)) {
    days.push({ label: whenLabel({ date: keep, time: '' }).replace(/, $/, ''), value: keep });
  }
  return days;
}

/** «Сегодня, 08:00», «Вчера, 21:30», «пн, 21 сент., 09:15». */
export function whenLabel(when: IntakeWhen): string {
  const [y, m, d] = when.date.split('-').map(Number);
  const day = new Date(y, m - 1, d);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const daysAgo = Math.round((today.getTime() - day.getTime()) / 86400000);
  return `${dayLabel(day, daysAgo)}, ${when.time}`;
}

/** «сегодня в 08:00», «вчера в 21:30»: for a sentence. */
export function whenPhrase(when: IntakeWhen): string {
  return whenLabel(when).replace(/, (\d\d:\d\d)$/, ' в $1').toLowerCase();
}

/** A moment some minutes ago, from the local wall clock: «15 минут назад», «час назад». */
export function minutesAgo(minutes: number): IntakeWhen {
  const at = new Date(Date.now() - minutes * 60_000);
  return { date: formatDate(at), time: `${pad(at.getHours())}:${pad(at.getMinutes())}` };
}

/** Now, as an IntakeWhen, from the local wall clock. */
export function nowWhen(): IntakeWhen {
  const now = new Date();
  return { date: formatDate(now), time: `${pad(now.getHours())}:${pad(now.getMinutes())}` };
}
