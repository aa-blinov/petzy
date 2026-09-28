import { isAxiosError } from 'axios';

interface ApiErrorPayload {
  error?: string;
  message?: string;
  detail?: string;
}

/** Shown when the request never reached the server. */
export const OFFLINE_MESSAGE = 'Нет связи с интернетом. Ничего не сохранилось, попробуйте ещё раз, когда связь появится';
export const NO_ANSWER_MESSAGE = 'Сервер не ответил. Попробуйте ещё раз через минуту';

/** Extracts the backend's `{ error }`/`{ message }`/`{ detail }` body from
 * a failed axios request. A request that got no answer at all (offline,
 * timeout, server down) says so instead of the caller's `fallback`, which
 * reads like the data was wrong. Anything else falls back to `fallback`. */
export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (isAxiosError<ApiErrorPayload>(error)) {
    if (!error.response) {
      return typeof navigator !== 'undefined' && navigator.onLine === false ? OFFLINE_MESSAGE : NO_ANSWER_MESSAGE;
    }
    const data = error.response.data;
    if (data && typeof data === 'object' && !Array.isArray(data)) {
      const text = data.error || data.message || data.detail;
      if (text) return text;
    }
    // A proxy's own page (502, 504) or an empty body: the server is down.
    if (error.response.status >= 500) return NO_ANSWER_MESSAGE;
    return fallback;
  }
  return fallback;
}
