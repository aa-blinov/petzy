import { isAxiosError } from 'axios';

interface ApiErrorPayload {
  error?: string;
  message?: string;
  detail?: string;
}

/** Extracts the backend's `{ error }`/`{ message }`/`{ detail }` body from
 * a failed axios request, falling back to `fallback` for anything else
 * (network errors, non-axios exceptions). */
export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (isAxiosError<ApiErrorPayload>(error)) {
    const data = error.response?.data;
    return data?.error || data?.message || data?.detail || fallback;
  }
  return fallback;
}
