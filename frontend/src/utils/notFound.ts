import { httpStatus } from '../services/api';

/**
 * The server answered, and what was asked for is not there: 404, or 422 for an address whose id is not even an id
 * (`/medications/zzz/edit`). That is a «не найдено» to say, and «Повторить» cannot change it. No answer at all and a 5xx are
 * not this: they keep their retry.
 */
export function isMissing(error: unknown): boolean {
  const status = httpStatus(error);
  return status === 404 || status === 422;
}

/** The same for a pet, where 403 (not the person's pet) reads as gone too: the screen says so in the same words. */
export function isPetGone(error: unknown): boolean {
  return isMissing(error) || httpStatus(error) === 403;
}
