/**
 * Unified toast helpers.
 *
 * Wraps antd-mobile's Toast so every message in the app:
 *   - sits at the bottom of the screen (not centred over it, which is
 *     antd's default and reads like a modal system alert)
 *   - auto-dismisses after 1.6s for neutral / 2.4s for failures
 *   - uses the same icon vocabulary as the rest of the UI
 *
 * Before this was adopted, 41 call sites invoked Toast.show directly:
 * 37 of them inherited antd's `position: 'center'` while 4 passed
 * 'bottom', and success durations came in five different values
 * (unset, 1000, 1500, 1600, 2000). Route every message through here so
 * the same kind of message always looks and lasts the same.
 */

import { Toast } from 'antd-mobile';

const COMMON = {
  position: 'bottom' as const,
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
    return show('success', message, 1600, options);
  },
  /** Failures and validation errors — held longer so they can be read. */
  failure(message: string, options?: ToastOptions) {
    return show('fail', message, 2400, options);
  },
  /** Neutral notices with no icon. */
  info(message: string, options?: ToastOptions) {
    return show(undefined, message, 1600, options);
  },
  /** Indeterminate progress; the caller closes the returned handler. */
  loading(message: string, options?: ToastOptions) {
    return show('loading', message, 0, options);
  },
};
