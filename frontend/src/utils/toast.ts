/**
 * Unified toast helpers.
 *
 * Wraps antd-mobile's Toast so every message in the app:
 *   - is centred on screen (antd's own default)
 *   - auto-dismisses after 2s for confirmations and notices, 4s for failures
 *   - uses the same icon vocabulary as the rest of the UI
 *
 * Before this was adopted, 41 call sites invoked Toast.show directly:
 * 37 of them inherited antd's `position: 'center'` while 4 passed
 * 'bottom', and success durations came in five different values
 * (unset, 1000, 1500, 1600, 2000). Route every message through here so
 * the same kind of message always looks and lasts the same.
 *
 * This used to pin every toast to `position: 'bottom'` (`top: 80%`) to
 * avoid looking like a centred modal alert. In practice that only
 * works for a short text-only toast — the icon variant (success/fail)
 * is a much taller box, and at 80% down the screen its bottom edge
 * crowds the bottom tab bar, landing in an awkward middle ground that
 * reads as neither "docked at the bottom" nor "centred" — just
 * mispositioned. Centring is the one placement that looks right at
 * every toast height.
 */

import { Toast } from 'antd-mobile';
import { announce } from './announce';

// How long a message stays. A short confirmation with nothing to press is
// read in about two seconds (Android's own Toast: 2 s); a failure has to be
// read and understood, and Material's floor for anything the user may have
// to act on is 4 s. A toast never holds anything up: a form that saved
// leaves at once and the toast stays over the screen it returns to.
const CONFIRM_MS = 2000;
const FAILURE_MS = 4000;

const COMMON = {
  maskClassName: 'app-toast-mask',
};

export interface ToastOptions {
  /** Override the default dismiss time (ms). */
  duration?: number;
  /** Runs once the toast has finished closing. */
  afterClose?: () => void;
}

function show(
  icon: 'success' | 'fail' | 'loading' | undefined,
  message: string,
  defaultDuration: number,
  options?: ToastOptions,
) {
  // The toast itself is silent for screen readers; say it aloud too.
  announce(message, icon === 'fail' ? 'assertive' : 'polite');
  return Toast.show({
    ...COMMON,
    ...(icon ? { icon } : {}),
    content: message,
    duration: options?.duration ?? defaultDuration,
    ...(options?.afterClose ? { afterClose: options.afterClose } : {}),
  });
}

export const showToast = {
  /** Confirmations: "Запись удалена", "Принято!". */
  success(message: string, options?: ToastOptions) {
    return show('success', message, CONFIRM_MS, options);
  },
  /** Failures and validation errors — held longer so they can be read. */
  failure(message: string, options?: ToastOptions) {
    return show('fail', message, FAILURE_MS, options);
  },
  /** Neutral notices with no icon. */
  info(message: string, options?: ToastOptions) {
    return show(undefined, message, CONFIRM_MS, options);
  },
  /** Indeterminate progress; the caller closes the returned handler. */
  loading(message: string, options?: ToastOptions) {
    return show('loading', message, 0, options);
  },
};
