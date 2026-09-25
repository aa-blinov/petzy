/**
 *Format date+time strings as natural Russian relative time.

Backend stores date_time as ``YYYY-MM-DD HH:MM`` (naive local time).
This module converts such strings into human-friendly forms:

  - "сегодня в 08:00"
  - "вчера в 19:00"
  - "3 дня назад"
  - "15 сентября"  (same year, not today/yesterday)
  - "15 сентября 2025"  (different year)

Use this anywhere a record's date_time is rendered for the user.

 */


export const MONTHS_GENITIVE = [
  "января", "февраля", "марта", "апреля", "мая", "июня",
  "июля", "августа", "сентября", "октября", "ноября", "декабря",
]


function _parseDate(dateStr: string): { y: number; m: number; d: number; hh: number; mm: number } | null {
  // Accept "YYYY-MM-DD HH:MM" or "YYYY-MM-DD" — match what the backend emits.
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}))?/.exec(dateStr);
  if (!m) return null;
  return {
    y: Number(m[1]),
    m: Number(m[2]),
    d: Number(m[3]),
    hh: Number(m[4] ?? "0"),
    mm: Number(m[5] ?? "0"),
  };
}


/**
 * Parse a backend `date_time` string into a Date in the viewer's own
 * timezone.
 *
 * The backend emits a naive local wall clock — `YYYY-MM-DD HH:MM`, or
 * just `YYYY-MM-DD` — so the only correct reading is to build the Date
 * from the parts. Handing either form straight to `new Date()` is wrong
 * in a different way for each:
 *
 *   - `new Date("2026-09-16")` is an ISO date-only form, which the spec
 *     says is UTC. Formatted in a negative-offset zone it renders as the
 *     *previous* day — a chart bar for the 16th is labelled "15 сент."
 *     in New York.
 *   - `new Date("2026-09-16 08:00")` is not ISO at all (ISO needs a `T`),
 *     so its handling is implementation-defined; engines happen to read
 *     it as local time, but nothing guarantees that.
 *
 * Returns null when the string doesn't match, so callers can fall back
 * to showing the raw value rather than "Invalid Date".
 */
export function parseRecordDate(dateStr: string): Date | null {
  const p = _parseDate(dateStr);
  if (!p) return null;
  return new Date(p.y, p.m - 1, p.d, p.hh, p.mm);
}


function _daysAgo(target: { y: number; m: number; d: number }, today: { y: number; m: number; d: number }): number {
  // Compute the difference in calendar days at local midnight.
  const t = new Date(target.y, target.m - 1, target.d).getTime();
  const n = new Date(today.y, today.m - 1, today.d).getTime();
  return Math.round((n - t) / 86_400_000);
}


/** "сегодня в 08:00", "вчера", "3 дня назад", "15 сентября" / "15 сентября 2025". */
export function formatRelativeDateTime(dateStr: string, now: Date = new Date()): string {
  const parsed = _parseDate(dateStr);
  if (!parsed) return dateStr;

  const today = { y: now.getFullYear(), m: now.getMonth() + 1, d: now.getDate() };
  const days = _daysAgo(parsed, today);
  const time = `${String(parsed.hh).padStart(2, "0")}:${String(parsed.mm).padStart(2, "0")}`;

  if (days === 0) return `сегодня в ${time}`;
  if (days === 1) return `вчера в ${time}`;
  if (days > 1 && days < 5) return `${days} дня назад`;
  if (days >= 5 && days < 365) return `${days} дней назад`;

  const monthName = MONTHS_GENITIVE[parsed.m - 1];
  if (parsed.y === today.y) return `${parsed.d} ${monthName}`;
  return `${parsed.d} ${monthName} ${parsed.y}`;
}


/** Just the date part: "сегодня", "вчера", "3 дня назад", "15 сентября". */
export function formatRelativeDate(dateStr: string, now: Date = new Date()): string {
  const parsed = _parseDate(dateStr);
  if (!parsed) return dateStr;

  const today = { y: now.getFullYear(), m: now.getMonth() + 1, d: now.getDate() };
  const days = _daysAgo(parsed, today);

  if (days === 0) return "сегодня";
  if (days === 1) return "вчера";
  if (days > 1 && days < 5) return `${days} дня назад`;
  if (days >= 5 && days < 365) return `${days} дней назад`;

  const monthName = MONTHS_GENITIVE[parsed.m - 1];
  if (parsed.y === today.y) return `${parsed.d} ${monthName}`;
  return `${parsed.d} ${monthName} ${parsed.y}`;
}


/** "2 часа назад", "15 минут назад", "только что". */
export function formatRelativeShort(dateStr: string, now: Date = new Date()): string {
  const parsed = _parseDate(dateStr);
  if (!parsed) return dateStr;

  const target = new Date(parsed.y, parsed.m - 1, parsed.d, parsed.hh, parsed.mm);
  const diffMs = now.getTime() - target.getTime();
  if (diffMs < 60_000) return "только что";
  const minutes = Math.floor(diffMs / 60_000);
  if (minutes < 60) return `${minutes} мин назад`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} ч назад`;
  const days = Math.floor(hours / 24);
  return `${days} дн назад`;
}


/**
 * Compute a pet's age from a ``YYYY-MM-DD`` birth date.
 * Returns e.g. "5 лет", "8 месяцев", "3 недели" — empty string if invalid.
 */
export function computePetAge(birthDateStr: string, now: Date = new Date()): string {
  if (!birthDateStr) return "";
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(birthDateStr);
  if (!m) return "";
  const birth = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  if (Number.isNaN(birth.getTime())) return "";

  const years = now.getFullYear() - birth.getFullYear();
  const monthDelta = now.getMonth() - birth.getMonth();
  let totalMonths = years * 12 + monthDelta;
  if (now.getDate() < birth.getDate()) totalMonths -= 1;
  if (totalMonths < 0) return "";

  if (totalMonths < 1) {
    const days = Math.max(0, Math.floor((now.getTime() - birth.getTime()) / 86_400_000));
    if (days < 7) return `${days} ${pluralRu(days, "день", "дня", "дней")}`;
    const weeks = Math.floor(days / 7);
    return `${weeks} ${pluralRu(weeks, "неделя", "недели", "недель")}`;
  }
  if (totalMonths < 12) {
    return `${totalMonths} ${pluralRu(totalMonths, "месяц", "месяца", "месяцев")}`;
  }
  const y = Math.floor(totalMonths / 12);
  return `${y} ${pluralRu(y, "год", "года", "лет")}`;
}


/** Russian plural form helper: 1 "год", 2 "года", 5 "лет". */
export function pluralRu(n: number, one: string, few: string, many: string): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
  return many;
}