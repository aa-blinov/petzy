import type { MedicalKind, ParasiteTarget } from '../services/medicalRecords.service';

/**
 * What a visit was for and what a procedure was, as the groups of the sheet that opens from the title row. They are
 * suggestions, not a list to pick from: the person can write their own reason, and the pet's earlier ones come first.
 */
export const OCCASION_GROUPS: Record<'visit' | 'procedure', { key: string; label: string; items: string[] }[]> = {
  visit: [
    { key: 'planned', label: 'По плану', items: ['Плановый осмотр', 'Вакцинация', 'Повторный приём', 'Сдача анализов', 'Снятие швов'] },
    {
      key: 'worry',
      label: 'Что-то беспокоит',
      items: ['Травма', 'Не ест, вялость', 'Рвота, диарея', 'Хромота', 'Зуд, проблемы с кожей', 'Кашель, дыхание'],
    },
  ],
  procedure: [
    {
      key: 'common',
      label: 'Частое',
      items: ['Стерилизация', 'Кастрация', 'Чистка зубов', 'УЗИ', 'Рентген', 'Удаление образования', 'Анализ крови', 'Капельница'],
    },
  ],
};

/** What a well-known treatment is for, so that the form can put «От чего» in itself. Only products with one plain purpose
    are listed (a combined one, or one used for several things, is left to the person); the form shows the choice as made
    and it is one tap to change. */
const TARGET_OF: [string, ParasiteTarget][] = [
  ['бравекто', 'fleas_ticks'],
  ['нексгард', 'fleas_ticks'],
  ['симпарика', 'fleas_ticks'],
  ['фронтлайн', 'fleas_ticks'],
  ['адвантикс', 'fleas_ticks'],
  ['дронтал', 'worms'],
  ['мильбемакс', 'worms'],
  ['празицид', 'worms'],
  ['прадакс', 'worms'],
  ['азинокс', 'worms'],
  ['адвокат', 'both'],
];

/** The treatments the list offers, by what they are for: the same products as `TARGET_OF`, with the names as sold. */
export const PARASITE_PRODUCTS: { name: string; target: ParasiteTarget }[] = [
  { name: 'Бравекто', target: 'fleas_ticks' },
  { name: 'Нексгард', target: 'fleas_ticks' },
  { name: 'Симпарика', target: 'fleas_ticks' },
  { name: 'Фронтлайн', target: 'fleas_ticks' },
  { name: 'Адвантикс', target: 'fleas_ticks' },
  { name: 'Дронтал Плюс', target: 'worms' },
  { name: 'Мильбемакс', target: 'worms' },
  { name: 'Празицид', target: 'worms' },
  { name: 'Прадакс', target: 'worms' },
  { name: 'Азинокс', target: 'worms' },
  { name: 'Адвокат', target: 'both' },
];

export function parasiteTargetOf(title: string): ParasiteTarget | null {
  const name = title.trim().toLowerCase();
  if (!name) return null;
  return TARGET_OF.find(([product]) => name.startsWith(product))?.[1] ?? null;
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

/** The interval put in the new record's «Следующая» for it, by kind: the usual one, one tap from gone. */
export const DEFAULT_REPEAT: Partial<Record<MedicalKind, { months?: number; years?: number }>> = {
  vaccination: { years: 1 },
  parasite: { months: 3 },
};

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
