/**
 * Deleting a record from the history, with «Отменить» instead of «Вы
 * уверены?».
 *
 * A record can't be brought back once the server has deleted it, so the
 * server is asked last: the record disappears from the lists at once, a
 * bar offers «Отменить» for a few seconds, and only when that time is up
 * (or a newer message replaces the bar, or the page is being closed) does
 * the real DELETE go out. Undo just shows the record again; nothing was
 * ever sent. If the DELETE fails, the record comes back with a message.
 *
 * Lists filter their rows through `useHiddenRecords()`.
 */

import { useSyncExternalStore } from 'react';
import api from '../services/api';
import { showSnackbar } from './snackbar';
import { showToast } from './toast';

let hidden: ReadonlySet<string> = new Set();
const listeners = new Set<() => void>();

function setHidden(next: Set<string>) {
  hidden = next;
  listeners.forEach((listener) => listener());
}
const hide = (id: string) => setHidden(new Set(hidden).add(id));
const show = (id: string) => {
  const next = new Set(hidden);
  next.delete(id);
  setHidden(next);
};

/** DELETEs waiting for their «Отменить» time to pass, by record id. */
const pending = new Map<string, string>();

/** Rows the lists must leave out: deleted, awaiting the real request. */
export function useHiddenRecords(): ReadonlySet<string> {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    () => hidden,
  );
}

export interface DeferredDelete {
  id: string;
  /** API path of the DELETE, relative to the API root: `/events/123`. */
  path: string;
  message: string;
  /** Said when the real DELETE fails and the record comes back. */
  failure?: string;
  /** «Отменить» was pressed. */
  onUndo?: () => void;
  /** Once the server has deleted it: refresh whatever shows the record. */
  onDeleted: () => Promise<unknown> | void;
}

export function deleteWithUndo({ id, path, message, failure, onUndo, onDeleted }: DeferredDelete): void {
  hide(id);
  pending.set(id, path);
  showSnackbar({
    message,
    tone: 'success',
    action: {
      label: 'Отменить',
      run: () => {
        pending.delete(id);
        show(id);
        onUndo?.();
      },
    },
    onDismiss: async (reason) => {
      if (reason === 'action' || !pending.has(id)) return;
      pending.delete(id);
      try {
        await api.delete(path);
        await onDeleted();
      } catch {
        showToast.failure(failure ?? 'Не удалось удалить, запись возвращена');
        show(id);
        return;
      }
      show(id);
    },
  });
}

// The tab is closing or the app is going away with deletions still waiting:
// send them now, in a way that survives the page (the user did ask for them).
function flushPending() {
  for (const [id, path] of pending) {
    pending.delete(id);
    try {
      void fetch(`${api.defaults.baseURL ?? '/api'}${path}`, { method: 'DELETE', credentials: 'include', keepalive: true });
    } catch {
      /* nothing more can be done as the page unloads */
    }
  }
}
window.addEventListener('pagehide', flushPending);
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'hidden') flushPending();
});
