import { useState } from 'react';

/**
 * Which fields of a hand-written form have been left, for showing their
 * errors as soon as they are known: after the user moves on from the
 * field, not only after pressing the button. (The forms on react-hook-form
 * get this from `mode: 'onTouched'`.)
 *
 *   const { touch, shows } = useTouched(submitted);
 *   <Input onBlur={touch('email')} />
 *   {shows('email') && emailError}
 */
export function useTouched(submitted: boolean) {
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  return {
    /** The field's onBlur. */
    touch: (name: string) => () => setTouched((current) => (current[name] ? current : { ...current, [name]: true })),
    /** Show this field's error: it was left, or the form was submitted. */
    shows: (name: string) => submitted || !!touched[name],
  };
}
