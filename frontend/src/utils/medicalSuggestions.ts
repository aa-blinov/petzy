import type { MedicalKind } from '../services/medicalRecords.service';

/**
 * Names offered as chips under the title field, to tap instead of type. They
 * are suggestions, not a list to pick from: anything can still be typed. A
 * pet's own earlier titles come first (see `suggestionsFor`), so the second
 * rabies shot is one tap.
 */
const COMMON: Record<MedicalKind, Record<string, string[]>> = {
  vaccination: {
    dog: ['Нобивак DHPPi', 'Нобивак Rabies', 'Эурикан DHPPi', 'Мультикан-8', 'Рабизин', 'Нобивак KC'],
    cat: ['Нобивак Tricat Trio', 'Нобивак Rabies', 'Пуревакс RCP', 'Фелоцел', 'Рабизин'],
    other: ['Бешенство', 'Комплексная прививка'],
  },
  parasite: {
    dog: ['Дронтал Плюс', 'Бравекто', 'Нексгард', 'Симпарика', 'Мильбемакс'],
    cat: ['Дронтал Плюс', 'Стронгхолд', 'Адвокат', 'Мильбемакс', 'Празицид'],
    other: ['Дронтал Плюс', 'Мильбемакс'],
  },
  visit: {
    other: ['Плановый осмотр', 'Вакцинация', 'Сдача анализов', 'Повторный приём', 'Травма'],
  },
  procedure: {
    other: ['Стерилизация', 'Кастрация', 'Чистка зубов', 'УЗИ', 'Рентген', 'Удаление образования'],
  },
};

const MAX_CHIPS = 6;

/** `own`: the titles this pet already has for the kind, newest first. */
export function suggestionsFor(kind: MedicalKind, species: string | undefined, own: string[]): string[] {
  const common = COMMON[kind][species ?? ''] ?? COMMON[kind].other ?? [];
  const seen = new Set<string>();
  const out: string[] = [];
  for (const title of [...own, ...common]) {
    const key = title.trim().toLowerCase();
    if (!key || seen.has(key)) continue;
    seen.add(key);
    out.push(title.trim());
  }
  return out.slice(0, MAX_CHIPS);
}

/** A date, moved on by months or years; the day stays in the month it lands in (31 Jan + 1 month is 28 or 29 Feb). */
export function addInterval(isoDate: string, interval: { months?: number; years?: number }): string {
  const [y, m, d] = isoDate.split('-').map(Number);
  const months = (interval.years ?? 0) * 12 + (interval.months ?? 0);
  const target = new Date(y, m - 1 + months, 1);
  const lastDay = new Date(target.getFullYear(), target.getMonth() + 1, 0).getDate();
  target.setDate(Math.min(d, lastDay));
  return `${target.getFullYear()}-${String(target.getMonth() + 1).padStart(2, '0')}-${String(target.getDate()).padStart(2, '0')}`;
}

/** The days between two ISO dates. */
export function daysBetween(fromIso: string, toIso: string): number {
  const a = new Date(`${fromIso}T00:00:00`).getTime();
  const b = new Date(`${toIso}T00:00:00`).getTime();
  return Math.round((b - a) / 86_400_000);
}

/** The repeat intervals offered as buttons next to «Следующая», by kind. */
export const REPEAT_CHOICES: Partial<Record<MedicalKind, { label: string; months?: number; years?: number }[]>> = {
  vaccination: [
    { label: 'Через 3 месяца', months: 3 },
    { label: 'Через год', years: 1 },
    { label: 'Через 3 года', years: 3 },
  ],
  parasite: [
    { label: 'Через месяц', months: 1 },
    { label: 'Через 3 месяца', months: 3 },
    { label: 'Через полгода', months: 6 },
  ],
};
