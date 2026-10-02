/** The IANA name of this device's time zone (Asia/Almaty), or undefined when
    the browser won't say. The server stores the clock a time was entered on
    and uses this name to show it on someone else's clock in an export. */
export function deviceTimeZone(): string | undefined {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || undefined;
  } catch {
    return undefined;
  }
}

/** The offset of a zone from UTC at an instant, in minutes. */
function offsetMinutes(timeZone: string, atMs: number): number {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone,
    hourCycle: 'h23',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).formatToParts(new Date(atMs));
  const n = (type: string) => Number(parts.find((p) => p.type === type)?.value);
  return Math.round((Date.UTC(n('year'), n('month') - 1, n('day'), n('hour'), n('minute'), n('second')) - atMs) / 60000);
}

/**
 * A record keeps the clock it was entered on, and the zone of that clock. The feed shows it on the clock of the
 * device that looks: 09:01 typed in Moscow is 11:01 in Almaty, and an hour-old feeding must not look like one of two
 * hours. «YYYY-MM-DD HH:MM» in, the same shape out; unchanged when the zone is the same or not known.
 */
export function toDeviceClock(stamp: string, fromTimeZone?: string | null): string {
  const to = deviceTimeZone();
  const match = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/.exec(stamp ?? '');
  if (!match || !fromTimeZone || !to || fromTimeZone === to) return stamp;
  try {
    const [y, mo, d, h, mi] = match.slice(1).map(Number);
    const asIfUtc = Date.UTC(y, mo - 1, d, h, mi);
    // The wall time in the source zone is the instant that zone's offset puts at that wall time (two steps settle it
    // around a change of offset).
    let instant = asIfUtc - offsetMinutes(fromTimeZone, asIfUtc) * 60000;
    instant = asIfUtc - offsetMinutes(fromTimeZone, instant) * 60000;
    const shifted = new Date(instant + offsetMinutes(to, instant) * 60000);
    const p = (v: number) => String(v).padStart(2, '0');
    return `${shifted.getUTCFullYear()}-${p(shifted.getUTCMonth() + 1)}-${p(shifted.getUTCDate())} ${p(shifted.getUTCHours())}:${p(shifted.getUTCMinutes())}`;
  } catch {
    return stamp;
  }
}
