import { useEffect, useRef } from 'react';
import { registerDraftProvider, takeDraft } from '../utils/sessionDraft';
import { showToast } from '../utils/toast';

interface SessionDraftOptions<T> {
  /** The form holds typed-in data worth keeping. */
  dirty: boolean;
  getValues: () => T;
  /** react-hook-form's reset: the draft goes in as unsaved changes on top of what the form started with. */
  reset: (values: T, options: { keepDefaultValues: boolean }) => void;
  /** The form has been filled with its own starting values (a loaded record, the blank), so a draft can go on top. */
  ready: boolean;
  /** The unsaved-changes guard's `release`: a session that ended must not be held back by «Выйти без сохранения?». */
  release: () => void;
}

/** A form keeps what was typed when the session runs out and takes it back after signing in. */
export function useSessionDraft<T>({ dirty, getValues, reset, ready, release }: SessionDraftOptions<T>): void {
  const dirtyNow = useRef(dirty);
  const valuesNow = useRef(getValues);
  const releaseNow = useRef(release);
  useEffect(() => {
    dirtyNow.current = dirty;
    valuesNow.current = getValues;
    releaseNow.current = release;
  });

  useEffect(
    () =>
      registerDraftProvider(() => {
        if (!dirtyNow.current) return undefined;
        releaseNow.current();
        return valuesNow.current();
      }),
    [],
  );

  const restored = useRef(false);
  useEffect(() => {
    if (!ready || restored.current) return;
    restored.current = true;
    const draft = takeDraft<T>();
    if (!draft) return;
    reset(draft, { keepDefaultValues: true });
    showToast.success('Вернули то, что вы вводили до выхода');
  }, [ready, reset]);
}
