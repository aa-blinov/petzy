import type { CSSProperties } from 'react';

interface PickerValueProps {
  /** The chosen value, as the row shows it; empty shows the placeholder. */
  value?: string | null;
  placeholder: string;
  id?: string;
  style?: CSSProperties;
}

/**
 * What a picker row (date, time, form of a medicine, category) shows.
 *
 * Text, not a read-only <input>: the row itself is the button, and an
 * input inside it was a second focus stop that screen readers could land
 * on, reading the row twice. As text the value is simply part of the
 * row's name: «Дата рождения, 12.03.2021».
 */
export function PickerValue({ value, placeholder, id, style }: PickerValueProps) {
  const empty = !value;
  // A caller's colour is for the value; the placeholder keeps its own.
  const { color, ...rest } = style ?? {};
  return (
    <span
      id={id}
      className={empty ? 'picker-value picker-value--empty' : 'picker-value'}
      style={empty ? rest : { ...rest, ...(color ? { color } : {}) }}
    >
      {empty ? placeholder : value}
    </span>
  );
}
