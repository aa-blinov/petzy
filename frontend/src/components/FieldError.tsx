import { useEffect, useId, useRef } from 'react';

/**
 * A validation message shown under its field, as a Form.Item
 * `description`.
 *
 * These used to go into Form.Item's `help`, which antd renders as a
 * popover behind a small "?" next to the label: a failed save showed
 * nothing unless you knew to tap it, and a screen reader never heard
 * it. This also marks the field itself: aria-invalid, plus
 * aria-describedby pointing at the message, on the input (or, for a
 * picker row, on the row that opens the picker).
 */
export function FieldError({ message }: { message?: string }) {
  const id = useId();
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!message) return;
    const item = ref.current?.closest('.adm-form-item');
    if (!item) return;
    const control = item.matches('[role="button"]')
      ? item
      : item.querySelector<HTMLElement>('input:not([type="hidden"]):not([readonly]), textarea:not([readonly]), [role="button"]');
    if (!control) return;
    control.setAttribute('aria-invalid', 'true');
    control.setAttribute('aria-describedby', id);
    return () => {
      control.removeAttribute('aria-invalid');
      if (control.getAttribute('aria-describedby') === id) control.removeAttribute('aria-describedby');
    };
  }, [id, message]);

  if (!message) return null;
  return (
    <div ref={ref} id={id} className="field-error">
      {message}
    </div>
  );
}
