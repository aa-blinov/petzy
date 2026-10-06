import { useEffect, useRef } from 'react';
import { registerDraftProvider, takeDraft } from '../utils/sessionDraft';
import { showToast } from '../utils/toast';

interface SessionDraftOptions<T> {
  /** The form holds typed-in data worth keeping. */
  dirty: boolean;
  /** The pet this form is about, so one pet's half-typed record is never handed to another's form.
   *  Null while the pet is still unknown: such a form owns no draft, and nothing is written for it. */
  petId: string | null;
  getValues: () => T;
  /** react-hook-form's reset: the draft goes in as unsaved changes on top of what the form started with. */
  reset: (values: T, options: { keepDefaultValues: boolean }) => void;
  /** The form has been filled with its own starting values (a loaded record, the blank), so a draft can go on top. */
  ready: boolean;
  /** The unsaved-changes guard's `release`: a session that ended must not be held back by «Выйти без сохранения?». */
  release: () => void;
}

/** A form keeps what was typed when the session runs out and takes it back after signing in.
 *
 *  The draft belongs to this screen and this pet: a form about one pet never hands its half-typed values to the
 *  same form about another, so the pet is part of the address. */
export function useSessionDraft<T>({ dirty, petId, getValues, reset, ready, release }: SessionDraftOptions<T>): void {
  const dirtyNow = useRef(dirty);
  const valuesNow = useRef(getValues);
  const releaseNow = useRef(release);
  const petNow = useRef(petId);
  useEffect(() => {
    dirtyNow.current = dirty;
    valuesNow.current = getValues;
    releaseNow.current = release;
    petNow.current = petId;
  });

  useEffect(
    () =>
      registerDraftProvider(() => {
        if (!dirtyNow.current) return undefined;
        releaseNow.current();
        return { owner: { path: window.location.pathname, petId: petNow.current }, values: valuesNow.current() };
      }),
    [],
  );

  const restored = useRef(false);
  useEffect(() => {
    if (!ready || restored.current || !petId) return;
    restored.current = true;
    // Не сразу, а после того, как форма подставит свои значения: её собственный reset стоит в эффекте ниже
    // этого, и без паузы он стирал бы восстановленное на следующем же кадре. Человек успевал увидеть
    // подсказку «вернули то, что вы вводили» и пустое поле.
    const timer = window.setTimeout(() => {
      const draft = takeDraft<T>({ path: window.location.pathname, petId });
      if (!draft) return;
      reset(draft, { keepDefaultValues: true });
      showToast.success('Вернули то, что вы вводили до выхода');
    }, 0);
    return () => window.clearTimeout(timer);
  }, [ready, reset, petId]);
}
