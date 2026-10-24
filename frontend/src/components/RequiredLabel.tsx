import type { ReactNode } from 'react';
import './RequiredLabel.css';

/** A label of a field that must be filled in: a red star the screen readers skip (the field itself says it is required). */
export function RequiredLabel({ children }: { children: ReactNode }) {
  return (
    <>
      {children}
      <span className="required-mark" aria-hidden="true"> *</span>
    </>
  );
}
