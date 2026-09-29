import type { ReactNode } from 'react';
import { FieldError } from './FieldError';

/** A field that isn't `always` counted shows its counter once the text gets
    this close to the limit. */
const NEAR_LIMIT = 0.8;

interface FieldNoteProps {
  /** Validation message; it takes the place of `hint`. */
  error?: string;
  /** A permanent explanation under the field. */
  hint?: ReactNode;
  /** The field's text and its `maxLength`, for the counter. */
  value?: string | null;
  max?: number;
  /** Count from the first character: for a paragraph (a note, a comment in
      a text area) you want to know how much room is left. A one-line field
      shows the counter only near its limit. */
  always?: boolean;
}

/**
 * What goes under a field, as a Form.Item `description`: the error (or
 * hint) on the left, a «37 / 100» counter on the right. Typing simply
 * stopped at the limit, with nothing to say why; now it says how much is
 * left, and that the limit is reached. Returns undefined when there is
 * nothing to show, so no empty row is left under the field.
 */
export function fieldNote({ error, hint, value, max, always }: FieldNoteProps): ReactNode | undefined {
  const length = (value ?? '').length;
  const counted = max !== undefined && (always || length >= max * NEAR_LIMIT);
  if (!error && !hint && !counted) return undefined;
  const atLimit = max !== undefined && length >= max;
  return (
    <div className="field-note">
      <div className="field-note__text">{error ? <FieldError message={error} /> : hint}</div>
      {counted && (
        <span className={`field-counter${atLimit ? ' field-counter--limit' : ''}`} aria-hidden>
          {length} / {max}
        </span>
      )}
      {atLimit && (
        // Spoken once, when the limit is reached; not on every keystroke.
        <span className="sr-only" role="status">
          Достигнут предел: {max} символов
        </span>
      )}
    </div>
  );
}
