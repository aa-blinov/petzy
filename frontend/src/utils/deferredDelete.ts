/**
 * Deleting a record from the history, with «Отменить» instead of «Вы
 * уверены?».
 *
 * A record can't be brought back once the server has deleted it, so the
 * server is asked last: the record disappears from the lists at once, a
 * bar offers «Отменить» for a few seconds, and only when that time is up
 * (or the page is being closed) does the real DELETE go out. Undo just shows
 * the record again; nothing was ever sent. If the DELETE fails, the record
 * comes back with a message.
 *
 * One bar for everything that is waiting. Two deletions in a row used to be
 * two bars, and the second pushed the first out: its message ended as
 * «вытеснена», which this file read as «the offer is over, delete it», so
 * the first record went to the server without anyone ever being able to
 * undo it. Now every record waiting shares one bar, «Отменить» brings all of
 * them back, and a message that isn't about deletion (a confirmation, a
 * failure) borrows the bar only while it is on screen: the offer comes back
 * when it ends, because a record nobody was shown may not be deleted just
 * because something else happened to appear.
 *
 * Lists filter their rows through `useHiddenRecords()`.
 */

import { useSyncExternalStore } from 'react';
import api from '../services/api';
import { getSnackbar, showSnackbar, subscribeSnackbar, updateSnackbar } from './snackbar';
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

/** DELETEs waiting for their «Отменить» time to pass, oldest first. */
const queue: DeferredDelete[] = [];

/** Which bar on screen is ours, if any. */
let barId: number | null = null;

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

/** One record waiting: its own words. Several at once: how many. */
function barMessage(): string {
  return queue.length > 1 ? `Удалено: ${queue.length}` : (queue[0]?.message ?? '');
}

/** Put the bar up if there is something to offer and the slot is free. */
function showBar(): void {
  if (barId !== null || queue.length === 0) return;
  if (getSnackbar()) return; // another message holds it: tried again when it ends
  showSnackbar({
    message: barMessage(),
    tone: 'success',
    action: {
      label: 'Отменить',
      run: () => {
        for (const item of queue.splice(0)) {
          show(item.id);
          item.onUndo?.();
        }
      },
    },
    onDismiss: (reason) => {
      barId = null;
      // Nothing was ever sent, so the undo did the whole job. A bar another
      // message took over is not a decision either: the offer returns with a
      // full time once that message has been read.
      if (reason === 'action' || reason === 'replaced') return;
      void sendQueue();
    },
  });
  barId = getSnackbar()?.id ?? null;
}

export function deleteWithUndo({ id, path, message, failure, onUndo, onDeleted }: DeferredDelete): void {
  hide(id);
  queue.push({ id, path, message, failure, onUndo, onDeleted });

  // Our bar may already be gone (another message took it over just now).
  if (barId !== null && getSnackbar()?.id !== barId) barId = null;

  if (barId !== null) {
    // A second deletion joins the bar that is already up, which says how many
    // there are now. Its time starts again: the newest request is the one
    // the person is looking at.
    updateSnackbar(barId, { message: barMessage() });
    return;
  }
  showBar();
}

async function sendQueue(): Promise<void> {
  const items = queue.splice(0);
  for (const item of items) {
    try {
      await api.delete(item.path);
      await item.onDeleted();
    } catch {
      showToast.failure(item.failure ?? 'Не удалось удалить, запись возвращена');
    }
    show(item.id);
  }
}

// The tab is closing or the app is going away with deletions still waiting:
// send them now, in a way that survives the page (the user did ask for them).
function flushPending() {
  for (const item of queue.splice(0)) {
    try {
      void fetch(`${api.defaults.baseURL ?? '/api'}${item.path}`, { method: 'DELETE', credentials: 'include', keepalive: true });
    } catch {
      /* nothing more can be done as the page unloads */
    }
  }
}
window.addEventListener('pagehide', flushPending);
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'hidden') flushPending();
});

// A message that isn't ours ended: the bar is free again, and the offer comes
// back if records are still waiting on it. Deferred by a microtask, because
// inside `showSnackbar` the slot looks free for an instant while the newer
// message is still being put up.
subscribeSnackbar(() => {
  void Promise.resolve().then(() => {
    if (barId === null && queue.length > 0) showBar();
  });
});