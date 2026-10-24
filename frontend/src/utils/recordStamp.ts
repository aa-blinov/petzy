import { utcMoment } from './dateUtils';

const pad = (n: number) => String(n).padStart(2, '0');

/** A moment the server stamps in UTC, as the person reads it on this device: «20.10.2026 15:25», the app's own date format. */
export function stampToRu(stamp: string): string {
  const moment = utcMoment(stamp);
  if (Number.isNaN(moment.getTime())) return stamp;
  return `${pad(moment.getDate())}.${pad(moment.getMonth() + 1)}.${moment.getFullYear()} ${pad(moment.getHours())}:${pad(moment.getMinutes())}`;
}
