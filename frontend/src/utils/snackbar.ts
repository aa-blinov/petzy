/**
 * Messages: one bar at the bottom, above the tab bar.
 *
 * Confirmations, errors and «Отменить» used to be two different things: a
 * box in the middle of the screen behind a dimming mask, and a separate
 * bar with an action. A message that needs no answer shouldn't cover the
 * page or hold anything up, so all of them are this bar now (Material's
 * snackbar): at the bottom, no mask, the screen stays usable, and it may
 * carry one action.
 *
 * One at a time: a newer message replaces the one on screen. The timer
 * lives here, not in the component, so a message still ends (and tells its
 * `onDismiss` how) when the component isn't mounted.
 *
 * How long it stays follows common practice: a confirmation is read in
 * about three seconds; an error has to be read and understood (Material's
 * floor for anything the user may act on is four; five leaves room to
 * read a sentence); a bar with an action stays long enough to notice a
 * mistake and reach for it.
 */

import { announce } from './announce';

export type SnackbarTone = 'success' | 'error' | 'info';
/** Why a message ended: its time ran out, its action was pressed, a newer
    message took its place, or it was closed by hand. */
export type DismissReason = 'timeout' | 'action' | 'replaced' | 'closed';

export const CONFIRM_MS = 3000;
export const ERROR_MS = 5000;
export const ACTION_MS = 6000;

export interface SnackbarRequest {
  message: string;
  tone?: SnackbarTone;
  /** Milliseconds; the default depends on the tone and on the action. */
  duration?: number;
  /** One button; its label is short, «Отменить». A rejected `run` keeps the bar. */
  action?: { label: string; run: () => Promise<void> | void };
  onDismiss?: (reason: DismissReason) => void;
}

export interface Snackbar extends SnackbarRequest {
  id: number;
  tone: SnackbarTone;
}

export interface SnackbarHandle {
  close: () => void;
}

let current: Snackbar | null = null;
let nextId = 1;
let timer: ReturnType<typeof setTimeout> | null = null;
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((listener) => listener());
}

function clearTimer() {
  if (timer) clearTimeout(timer);
  timer = null;
}

function dismiss(id: number, reason: DismissReason) {
  if (!current || current.id !== id) return;
  const ended = current;
  current = null;
  clearTimer();
  emit();
  ended.onDismiss?.(reason);
}

function durationFor(request: SnackbarRequest, tone: SnackbarTone): number {
  if (request.duration !== undefined) return request.duration;
  if (request.action) return ACTION_MS;
  return tone === 'error' ? ERROR_MS : CONFIRM_MS;
}

export function showSnackbar(request: SnackbarRequest): SnackbarHandle {
  if (current) dismiss(current.id, 'replaced');
  const tone = request.tone ?? 'info';
  const snackbar: Snackbar = { ...request, tone, id: nextId++ };
  current = snackbar;
  emit();
  // The bar is silent for screen readers; say it aloud too.
  announce(request.message, tone === 'error' ? 'assertive' : 'polite');
  const ms = durationFor(request, tone);
  if (ms > 0) timer = setTimeout(() => dismiss(snackbar.id, 'timeout'), ms);
  return { close: () => dismiss(snackbar.id, 'closed') };
}

/** Press the bar's action. Ends the message afterwards unless the action
    itself put a newer one up. Resolves false when the action failed. */
export async function runSnackbarAction(id: number): Promise<boolean> {
  const snackbar = current;
  if (!snackbar || snackbar.id !== id || !snackbar.action) return false;
  clearTimer();
  try {
    await snackbar.action.run();
  } catch {
    // Keep the bar for another try, with a fresh timer.
    if (current?.id === id) timer = setTimeout(() => dismiss(id, 'timeout'), durationFor(snackbar, snackbar.tone));
    return false;
  }
  dismiss(id, 'action');
  return true;
}

export function closeSnackbar(id: number) {
  dismiss(id, 'closed');
}

/** Change the message of the bar that is on screen (the same id). The time
    it had left starts again: this is a new thing to read, not the one that
    was nearly over. Does nothing once the bar has ended. */
export function updateSnackbar(id: number, patch: { message: string }): void {
  if (!current || current.id !== id) return;
  current = { ...current, ...patch };
  clearTimer();
  emit();
  announce(current.message, current.tone === 'error' ? 'assertive' : 'polite');
  const ms = durationFor(current, current.tone);
  if (ms > 0) timer = setTimeout(() => dismiss(id, 'timeout'), ms);
}

export function subscribeSnackbar(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function getSnackbar(): Snackbar | null {
  return current;
}
