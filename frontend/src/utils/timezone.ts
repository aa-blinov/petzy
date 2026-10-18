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

/** A moment with the offset of its zone at the end, «2026-10-18T08:12:00+05:00» or «…Z», as the server writes it now. */
const ZONED = /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})$/;

/** The calendar date a stamp carries, «YYYY-MM-DD», whether it has a zone or not. */
export function wallDate(stamp: string | null | undefined): string {
  return String(stamp ?? '').slice(0, 10);
}

/** The clock a stamp carries, «HH:MM», as it was entered: no conversion. */
export function wallTime(stamp: string | null | undefined): string {
  return String(stamp ?? '').slice(11, 16);
}

/** The zone to send with a moment someone typed: the device's own, or UTC when the browser does not name one. */
export function requiredZone(): string {
  return deviceTimeZone() ?? 'UTC';
}

const pad = (value: number) => String(value).padStart(2, '0');

/** The moment as a stamp with this device's offset now: «2026-10-18T08:12:33+05:00». */
export function zonedNowStamp(now: Date = new Date()): string {
  const offset = -now.getTimezoneOffset();
  const abs = Math.abs(offset);
  const sign = offset >= 0 ? '+' : '-';
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}${sign}${pad(Math.floor(abs / 60))}:${pad(abs % 60)}`;
}

/** The clock of a device zone at an instant, «YYYY-MM-DD HH:MM»; this device's own clock when the zone is not known. */
function clockAt(instant: number, zone: string | undefined): string {
  if (!zone) {
    const local = new Date(instant);
    return `${local.getFullYear()}-${pad(local.getMonth() + 1)}-${pad(local.getDate())} ${pad(local.getHours())}:${pad(local.getMinutes())}`;
  }
  const shifted = new Date(instant + offsetMinutes(zone, instant) * 60000);
  return `${shifted.getUTCFullYear()}-${pad(shifted.getUTCMonth() + 1)}-${pad(shifted.getUTCDate())} ${pad(shifted.getUTCHours())}:${pad(shifted.getUTCMinutes())}`;
}

/**
 * A record keeps the clock it was entered on, and the zone of that clock. The feed shows it on the clock of the
 * device that looks: 09:01 typed in Moscow is 11:01 in Almaty, and an hour-old feeding must not look like one of two
 * hours. A stamp with its offset is an exact moment, so it is converted from the offset. A stamp with no zone known
 * (saved before one was kept) keeps its clock as entered. The answer is always «YYYY-MM-DD HH:MM».
 */
export function toDeviceClock(stamp: string, fromTimeZone?: string | null): string {
  const to = deviceTimeZone();
  if (ZONED.test(stamp ?? '')) {
    if (!fromTimeZone) return `${wallDate(stamp)} ${wallTime(stamp)}`;
    const instant = new Date(stamp.replace(' ', 'T')).getTime();
    return Number.isNaN(instant) ? `${wallDate(stamp)} ${wallTime(stamp)}` : clockAt(instant, to);
  }
  const match = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/.exec(stamp ?? '');
  if (!match || !fromTimeZone || !to || fromTimeZone === to) return stamp;
  try {
    const [y, mo, d, h, mi] = match.slice(1).map(Number);
    const asIfUtc = Date.UTC(y, mo - 1, d, h, mi);
    // The wall time in the source zone is the instant that zone's offset puts at that wall time (two steps settle it
    // around a change of offset).
    let instant = asIfUtc - offsetMinutes(fromTimeZone, asIfUtc) * 60000;
    instant = asIfUtc - offsetMinutes(fromTimeZone, instant) * 60000;
    return clockAt(instant, to);
  } catch {
    return stamp;
  }
}
