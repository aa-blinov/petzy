import { useState, type ReactNode } from 'react';
import { Form, Picker } from 'antd-mobile';

import { PickerValue } from './PickerValue';

/** A row that shows its choice and opens a list to change it: the dropdown of a form where there are a few choices and no cloud of
    chips. `empty` is the label of «none» in the list, when none is allowed. */
export function PickerField({
  label,
  value,
  options,
  placeholder,
  empty,
  description,
  onChange,
}: {
  label: ReactNode;
  value: string;
  options: { label: string; value: string }[];
  placeholder: string;
  empty?: string;
  description?: ReactNode;
  onChange: (value: string) => void;
}) {
  const [open, setOpen] = useState(false);
  // The wheel is controlled: what it shows while it is turned is kept here until «Готово».
  const [draft, setDraft] = useState<string[] | null>(null);
  const columns = [empty ? [{ label: empty, value: '' }, ...options] : options];
  const shown = options.find((o) => o.value === value)?.label ?? '';
  return (
    <Form.Item label={label} clickable arrow description={description} onClick={() => {
        setDraft(null);
        setOpen(true);
      }}>
      <PickerValue value={shown} placeholder={placeholder} />
      <Picker
        columns={columns}
        visible={open}
        value={draft ?? [value]}
        onSelect={(val) => setDraft(val as string[])}
        onClose={() => setOpen(false)}
        onConfirm={(val) => {
          onChange((val[0] as string | undefined) ?? '');
          setDraft(null);
          setOpen(false);
        }}
        cancelText="Отмена"
        confirmText="Готово"
      />
    </Form.Item>
  );
}
