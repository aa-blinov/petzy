/** Doses marked while there was no connection.
 *
 *  A dose is marked with a thumb, often in a place with poor signal. Losing it is worse than sending it late, so a mark
 *  that could not reach the server (no answer at all, not a refusal) is kept on the phone, shown as «Не отправлено»,
 *  and sent by itself once the connection is back. A dose the server already has (the request got through but its
 *  answer did not) comes back as «уже отмечен»: it is dropped, so nothing is written twice, and said, so the person
 *  knows the dose is in the diary.
 *
 *  Each dose is kept under the login it was marked for. Only that login sends it or sees it as pending: see
 *  intakeQueueOwner.ts for the rules. Signing out leaves the queue as it is. */
import { isAxiosError } from 'axios';
import { useMemo, useSyncExternalStore } from 'react';
import type { QueryClient } from '@tanstack/react-query';
import { medicationsService, type IntakeInput } from '../services/medications.service';
import type { SessionResponse } from '../services/auth.service';
import { httpStatus } from '../services/api';
import { SESSION_QUERY_KEY, useSession } from '../hooks/useSession';
import { refreshAfterIntake } from './intakeViews';
import { showToast } from './toast';
import { claimUnowned, queueOf } from './intakeQueueOwner';

const KEY = 'petzy:pendingIntakes';

export interface PendingIntake {
  key: string;
  /** The login the dose was marked under. Entries written before this field have none. */
  owner?: string;
  medicationId: string;
  name: string;
  /** Whose pet the dose was for: the queue can outlive the screen it was made on, so the
   *  pet open right now is no proof. Older entries have no pet and are read without it. */
  petName?: string;
  input: IntakeInput;
}

let items: PendingIntake[] = read();
/** Whether localStorage took the last write. When it did not, this tab's memory is the only copy of the queue
 *  and reading the storage would hand back nothing to build the next write from. */
let inStorage = true;
const listeners = new Set<() => void>();

function read(): PendingIntake[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(KEY) ?? '[]');
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function set(next: PendingIntake[]) {
  items = next;
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
    inStorage = true;
  } catch {
    /* storage unavailable: the queue lives until the page closes */
    inStorage = false;
  }
  listeners.forEach((listener) => listener());
}

/** The queue a write starts from: what the other tabs of this browser left in the storage, and this tab's own
 *  memory when there is no storage to leave it in. */
function current(): PendingIntake[] {
  return inStorage ? read() : items;
}

/** The request never got an answer: the phone has no connection, or the server did not reply in time. */
export function isOffline(err: unknown): boolean {
  return isAxiosError(err) && !err.response;
}

/** Keeps a dose marked with no connection, for the login it was marked under. */
export function enqueueIntake(owner: string, medicationId: string, name: string, input: IntakeInput, petName?: string): void {
  // The queue lives in localStorage, which the other tabs of this browser write too, while `items` is what was
  // stored when this one loaded: appending to it would drop a dose marked in a tab open longer than this.
  set([
    ...current(),
    { key: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`, owner, medicationId, name, petName, input },
  ]);
}

/** The queue as the person signed in now sees it: their own doses, and any not yet claimed by a login. */
export function usePendingIntakes(): readonly PendingIntake[] {
  const { username } = useSession();
  const all = useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    () => items,
  );
  return useMemo(() => queueOf(all, username), [all, username]);
}

let flushing = false;

/** The login the app is signed in as right now, from the session it already holds (null when signed out or not known). */
function signedInAs(queryClient: QueryClient): string | null {
  return queryClient.getQueryData<SessionResponse>(SESSION_QUERY_KEY)?.username ?? null;
}

/** Sends the signed-in person's own doses, oldest first. Stops at the first one that cannot get through now, and as soon
 *  as the login changes, so a dose never goes out under someone else's session. Other logins' doses are not touched. */
export async function flushPendingIntakes(queryClient: QueryClient): Promise<void> {
  const login = signedInAs(queryClient);
  if (!login || flushing) return;
  // Another tab may have marked a dose while this one was open: send what is stored now, not the snapshot.
  set(current());
  // Entries from before owners were recorded belong to the first login that sends them.
  const claimed = claimUnowned(items, login);
  if (claimed !== items) set(claimed);
  const mine = items.filter((item) => item.owner === login);
  if (mine.length === 0) return;
  flushing = true;
  let sent = 0;
  try {
    for (const item of mine) {
      if (signedInAs(queryClient) !== login) break;
      try {
        await medicationsService.logIntake(item.medicationId, item.input);
        sent += 1;
      } catch (err) {
        // No answer, or the session has ended: the mark is not refused, so it stays queued for its owner.
        if (isOffline(err) || httpStatus(err) === 401) break;
        if (httpStatus(err) === 409) {
          // Already there: the first try did reach the server. The mark is
          // not lost, it is written twice if we keep it, and the person has
          // to be told that it is already in the diary.
          showToast.info(`${item.name}: отметка уже есть в журнале`);
        } else {
          // Refused for good: not kept, and said.
          showToast.failure(`${item.name}: отметку не удалось отправить, отметьте приём ещё раз`);
        }
      }
      // The dose leaves the stored queue, which may have grown while the server was thinking.
      set(current().filter((i) => i.key !== item.key));
    }
  } finally {
    flushing = false;
  }
  if (sent > 0) {
    await refreshAfterIntake(queryClient);
    showToast.success(sent === 1 ? 'Отметка отправлена' : `Отправлено отметок: ${sent}`);
  }
}
