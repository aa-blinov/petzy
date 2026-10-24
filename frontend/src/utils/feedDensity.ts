/** How long the feed shows the pet's full card: the first week on this device. After it the card is one line (a thumb,
 *  the name, the age), so the history starts where the person is looking for it, not below a card they know by heart. */
export const FULL_CARD_DAYS = 7;
const KEY = 'petzy:feedFirstSeen';

const pad = (n: number) => String(n).padStart(2, '0');
const isoDay = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

/** True when `firstSeen` (YYYY-MM-DD, as the person saw the day) is `days` or more days before `now`. A date that cannot be
 *  read is not old: the full card stays. */
export function seenLongEnough(firstSeen: string | null, now: Date, days = FULL_CARD_DAYS): boolean {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(firstSeen ?? '');
  if (!m) return false;
  const start = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  return Math.round((today.getTime() - start.getTime()) / 86_400_000) >= days;
}

/** The day the feed was first opened on this device is stored once; whether that was long enough ago is the answer.
 *  Without storage (private mode) the card is always the full one. */
export function readDenseFeedCard(now: Date = new Date()): boolean {
  try {
    const stored = localStorage.getItem(KEY);
    if (!stored) {
      localStorage.setItem(KEY, isoDay(now));
      return false;
    }
    return seenLongEnough(stored, now);
  } catch {
    return false;
  }
}
