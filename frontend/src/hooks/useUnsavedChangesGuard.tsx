import { useEffect, useRef, type ReactNode } from 'react';
import { useBlocker } from 'react-router-dom';
import { Dialog } from 'antd-mobile';

/**
 * A form that holds typed-in data asks before it is left.
 *
 * Nothing did: the edge swipe, the back arrow, a tab in the bar or the
 * browser's own back all dropped what had been typed, without a word. While
 * `dirty`, leaving the screen (to another page, by any of those ways) shows
 * «Выйти без сохранения?» and waits; closing or reloading the tab gets the
 * browser's own warning.
 *
 * Returns the dialog to render once in the form, and `release`: call it
 * right before navigating away after a successful save or delete, which
 * must not ask.
 */
export function useUnsavedChangesGuard(dirty: boolean): { dialog: ReactNode; release: () => void } {
  const dirtyNow = useRef(dirty);
  const released = useRef(false);
  useEffect(() => {
    dirtyNow.current = dirty;
  }, [dirty]);

  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      dirtyNow.current && !released.current && currentLocation.pathname !== nextLocation.pathname,
  );

  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [dirty]);

  const dialog = (
    <Dialog
      visible={blocker.state === 'blocked'}
      title="Выйти без сохранения?"
      content="То, что вы ввели, пропадёт"
      getContainer={() => document.body}
      onClose={() => blocker.reset?.()}
      actions={[
        // Destructive action first, cancel second: the app's dialog order.
        { key: 'leave', text: 'Выйти', danger: true, onClick: () => blocker.proceed?.() },
        { key: 'stay', text: 'Остаться', bold: true, onClick: () => blocker.reset?.() },
      ]}
    />
  );

  return {
    dialog,
    release: () => {
      released.current = true;
    },
  };
}
