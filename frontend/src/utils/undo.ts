/**
 * «Отменить» after an action taken by mistake (a dose marked with a stray
 * tap): a bar at the bottom for a few seconds instead of a confirmation
 * before every action. One bar at a time, shown by <UndoSnackbar /> in
 * App; a newer message replaces the one on screen.
 */

export interface UndoRequest {
  message: string;
  /** Reverts the action; rejects to keep the bar's error toast. */
  onUndo: () => Promise<void>;
}

type Listener = (request: UndoRequest | null) => void;

const listeners = new Set<Listener>();

export function showUndo(request: UndoRequest): void {
  listeners.forEach((listener) => listener(request));
}

export function subscribeUndo(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
