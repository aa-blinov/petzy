/**
 * Unified toast helpers.
 *
 * Wraps antd-mobile's Toast so every message in the app:
 *   - sits at the bottom of the screen (not the top, which obscures the
 *     navbar and feels like a system alert)
 *   - auto-dismisses after 1.6s for neutral / 2.4s for failures
 *   - uses the same icon vocabulary as the rest of the UI
 *
 * `showToast.success(...)` is the workhorse — covers the "Запись удалена",
 * "Принято!" etc. flow that currently calls Toast.show with a success
 * icon and 1500 ms duration in 12+ places.
 */

import { Toast } from 'antd-mobile';

const COMMON = {
  position: 'bottom' as const,
  maskClassName: 'app-toast-mask',
};

export const showToast = {
  success(message: string, duration = 1600) {
    return Toast.show({
      ...COMMON,
      icon: 'success',
      content: message,
      duration,
    });
  },
  failure(message: string, duration = 2400) {
    return Toast.show({
      ...COMMON,
      icon: 'fail',
      content: message,
      duration,
    });
  },
  info(message: string, duration = 1600) {
    return Toast.show({
      ...COMMON,
      content: message,
      duration,
    });
  },
};
