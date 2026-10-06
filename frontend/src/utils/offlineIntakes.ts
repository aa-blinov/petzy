/** Doses marked while there was no connection.
 *
 *  A dose is marked with a thumb, often in a place with poor signal. Losing it is worse than sending it late, so a mark
 *  that could not reach the server (no answer at all, not a refusal) is kept on the phone, shown as «Не отправлено»,
 *  and sent by itself once the connection is back. A dose the server already has (the request got through but its
 *  answer did not) comes back as «уже отмечен»: it is dropped, so nothing is written twice, and said, so the person
 *  knows the dose is in the diary. */
import { isAxiosError } from 'axios';
import { useSyncExternalStore } from 'react';
import type { QueryClient } from '@tanstack/react-query';
import { medicationsService, type IntakeInput } from '../services/medications.service';
import { refreshAfterIntake } from './intakeViews';
import { showToast } from './toast';

const KEY = 'petzy:pendingIntakes';

export interface PendingIntake {
  key: string;
  medicationId: string;
  name: string;
  /** Whose pet the dose was for: the queue can outlive the screen it was made on, so the
   *  pet open right now is no proof. Older entries have no pet and are read without it. */
  petName?: string;
  input: IntakeInput;
}

let items: PendingIntake[] = read();
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
  } catch {
    /* storage unavailable: the queue lives until the page closes */
  }
  listeners.forEach((listener) => listener());
}

/** The request never got an answer: the phone has no connection, or the server did not reply in time. */
export function isOffline(err: unknown): boolean {
  return isAxiosError(err) && !err.response;
}

export function enqueueIntake(medicationId: string, name: string, input: IntakeInput, petName?: string): void {
  set([
    ...items,
    { key: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`, medicationId, name, petName, input },
  ]);
}

export function usePendingIntakes(): readonly PendingIntake[] {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    () => items,
  );
}

let flushing = false;

/** Sends what is waiting, oldest first; stops at the first one that still cannot get through. */
export async function flushPendingIntakes(queryClient: QueryClient): Promise<void> {
  if (flushing || items.length === 0) return;
  flushing = true;
  let sent = 0;
  try {
    for (const item of [...items]) {
      try {
        await medicationsService.logIntake(item.medicationId, item.input);
        sent += 1;
      } catch (err) {
        if (isOffline(err)) break;
        if (isAxiosError(err) && err.response?.status === 409) {
          // Already there: the first try did reach the server. The mark is
          // not lost, it is written twice if we keep it, and the person has
          // to be told that it is already in the diary.
          showToast.info(`${item.name}: отметка уже есть в журнале`);
        } else {
          // Refused for good: not kept, and said.
          showToast.failure(`${item.name}: отметку не удалось отправить, отметьте приём ещё раз`);
        }
      }
      set(items.filter((i) => i.key !== item.key));
    }
  } finally {
    flushing = false;
  }
  if (sent > 0) {
    await refreshAfterIntake(queryClient);
    showToast.success(sent === 1 ? 'Отметка отправлена' : `Отправлено отметок: ${sent}`);
  }
}
