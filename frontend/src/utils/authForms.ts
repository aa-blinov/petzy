import { useEffect, useState } from 'react';
import { isAxiosError } from 'axios';

/**
 * The sign-in and sign-up forms share two things: the server's password
 * rules, checked here so a mistake shows under the field rather than after a
 * round trip, and the wait a rate limit puts on the submit button.
 */

/** The error code web/auth.py `password_problem` would answer with, as words
 *  for the field. An empty password isn't a mistake yet, so nothing is said
 *  about it. The list of the most guessed passwords is left to the server:
 *  it is a dictionary, not a rule, and its answer arrives as the usual error
 *  text. */
export function passwordProblem(password: string, username = ''): string | null {
  if (!password) return null;
  if (password.length < 8) return 'Не короче 8 символов';
  // bcrypt hashes the first 72 bytes only, the rest is silently cut off. The bound is in
  // bytes and stays that way for the check; what the person is told is the server's own
  // wording, because "72 байта" is a fact about the hash, not about a password they chose.
  if (new TextEncoder().encode(password).length > 72) return 'Пароль слишком длинный';
  if (username && password.toLowerCase() === username.toLowerCase()) {
    return 'Пароль не должен совпадать с логином';
  }
  if (new Set(password).size < 3) return 'Нужно хотя бы три разных символа';
  return null;
}

/** How long the server asked to wait after a 429 (web/app.py puts it in the
 *  body as `retry_after`); 0 for anything else. */
export function retryAfterSeconds(err: unknown): number {
  if (!isAxiosError<{ retry_after?: number }>(err) || err.response?.status !== 429) return 0;
  const seconds = Number(err.response?.data?.retry_after);
  return Number.isFinite(seconds) && seconds > 0 ? seconds : 0;
}

/** The wait the server asked for, counted down, so a form can say it instead
 *  of letting a person spend the next attempts on the same refused button.
 *  `lock(err)` takes the failed request and reports whether it locked. */
export function useRetryLock() {
  const [until, setUntil] = useState(0);
  const [left, setLeft] = useState(0);

  useEffect(() => {
    if (!until) return;
    const tick = () => {
      const rest = Math.max(0, Math.ceil(until - Date.now() / 1000));
      setLeft(rest);
      if (rest === 0) setUntil(0);
    };
    tick();
    const timer = setInterval(tick, 1000);
    return () => clearInterval(timer);
  }, [until]);

  return {
    /** Seconds still to wait, 0 when the form is open. */
    left,
    lock: (err: unknown) => {
      const seconds = retryAfterSeconds(err);
      if (seconds) setUntil(Date.now() / 1000 + seconds);
      return seconds;
    },
  };
}

/** What a locked form says instead of a button that would be refused. */
export function retryNote(left: number): string | null {
  if (left <= 0) return null;
  return `Слишком много попыток с этого адреса. Повторите через ${left} с`;
}