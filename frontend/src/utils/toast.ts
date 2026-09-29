/**
 * Unified message helpers.
 *
 * Every message in the app goes through here, and all but «loading» are
 * the bottom bar of utils/snackbar.ts: no mask, no box over the middle of
 * the page, nothing held up. That is also why a form that has saved can
 * leave at once: the message follows the user to the next screen.
 *
 * Before this, 41 call sites invoked Toast.show directly (four different
 * positions, five success durations), and later a centred box and a
 * separate «Отменить» bar coexisted. One place now decides how a kind of
 * message looks and how long it stays (see snackbar.ts for the times).
 *
 * «loading» is the one exception: progress with no end yet is a centred
 * spinner that blocks nothing until the caller closes it.
 */

import { Toast } from 'antd-mobile';
import { showSnackbar, type SnackbarHandle } from './snackbar';

export interface ToastOptions {
  /** Override the default dismiss time (ms). */
  duration?: number;
  /** Runs once the message has ended, however it ended. */
  afterClose?: () => void;
}

function show(tone: 'success' | 'error' | 'info', message: string, options?: ToastOptions): SnackbarHandle {
  return showSnackbar({
    message,
    tone,
    duration: options?.duration,
    ...(options?.afterClose ? { onDismiss: options.afterClose } : {}),
  });
}

export const showToast = {
  /** Confirmations: "Запись удалена", "Принято!". */
  success(message: string, options?: ToastOptions) {
    return show('success', message, options);
  },
  /** Failures and validation errors: held longer so they can be read. */
  failure(message: string, options?: ToastOptions) {
    return show('error', message, options);
  },
  /** Neutral notices. */
  info(message: string, options?: ToastOptions) {
    return show('info', message, options);
  },
  /** Indeterminate progress; the caller closes the returned handler. */
  loading(message: string) {
    return Toast.show({ maskClassName: 'app-toast-mask', icon: 'loading', content: message, duration: 0 });
  },
};
