import type { ReactNode } from 'react';
import './ChoiceChips.css';

/** A row of choices to tap instead of type: the suggestions under a field, a «как обычно / изменилось» answer, the
    clinics of the profile. Labelled as a group, so that a screen reader says what the row is for. */
export function ChoiceChips({ label, flush = false, children }: { label: string; /** No space above: the row is the whole content of its field. */ flush?: boolean; children: ReactNode }) {
  return (
    <div role="group" aria-label={label} className={`choice-chips${flush ? ' choice-chips--flush' : ''}`}>
      {children}
    </div>
  );
}

/** One choice. `pressed` is the state, said to a screen reader as well as drawn; the target is the touch minimum even
    though the chip is drawn small. */
export function ChoiceChip({ pressed, onClick, children }: { pressed: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      className="choice-chip"
      aria-pressed={pressed}
      // A chip does not take the cursor from a field that has it: the field would be left, say so about what is still empty,
      // and the message would push the chip from under the finger before the tap lands.
      onMouseDown={(event) => event.preventDefault()}
      onClick={onClick}
    >
      {children}
    </button>
  );
}
