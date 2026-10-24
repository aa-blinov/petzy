import { getCurrentDate } from './dateUtils';

export const FUTURE_DATE_MESSAGE = 'Дата не может быть в будущем';

/** A date (`YYYY-MM-DD`, as the person sees it) is allowed when it is not set or not after today. */
export function notInFuture(value: string | undefined, today: string = getCurrentDate()): boolean {
  return !value || value <= today;
}
