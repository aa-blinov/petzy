import { useSyncExternalStore } from 'react';
import type { PetLook } from './petLook';

/**
 * The look being edited, while the settings page is open: the app shows it in place of the saved one, everywhere at once
 * (the page, the header, the tab bar), so what is seen there is what will be saved. Null when no one is editing.
 */
let current: PetLook | null = null;
const listeners = new Set<() => void>();

export function setPetLookPreview(look: PetLook | null): void {
  current = look;
  listeners.forEach((l) => l());
}

export function usePetLookPreview(): PetLook | null {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => current,
  );
}
