import { useState, type ReactNode } from 'react';
import { Form, Popup } from 'antd-mobile';
import { Check } from 'lucide-react';

import { DraggableSheetBody } from './DraggableSheetBody';
import { PickerValue } from './PickerValue';
import { hapticFeedback } from '../utils/haptic';
import './ChoiceSheetField.css';

export interface ChoiceOption {
  label: string;
  value: string;
}

/** The rows of a fixed list: the chosen one is marked, a tap on a row chooses it. A list with no «Готово»: nothing is accepted by
    pressing past it. */
export function ChoiceList({ options, value, onPick }: { options: ChoiceOption[]; value: string; onPick: (value: string) => void }) {
  return (
    <ul className="choice-sheet__list" role="listbox">
      {options.map((option) => {
        const chosen = option.value === value;
        return (
          <li key={option.value} role="presentation">
            <button
              type="button"
              role="option"
              aria-selected={chosen}
              className={`choice-sheet__row tap-feedback${chosen ? ' choice-sheet__row--chosen' : ''}`}
              onClick={() => onPick(option.value)}
            >
              <span className="choice-sheet__label">{option.label}</span>
              {chosen && <Check size={18} strokeWidth={2.4} aria-hidden />}
            </button>
          </li>
        );
      })}
    </ul>
  );
}

/**
 * A row of a form that shows its choice and opens a list of the few fixed choices there are (a category, a form of a medicine):
 * a tap on a row chooses it and closes the list. A wheel with «Готово» is for dates and times only: on a wheel the first item is
 * already under the finger, and «Готово» accepts it without a choice having been made.
 */
export function ChoiceSheetField({
  label,
  title,
  value,
  options,
  placeholder,
  description,
  required,
  disabled,
  onChange,
}: {
  label: ReactNode;
  /** The name of the sheet; the label when it is text. */
  title?: string;
  value: string;
  options: ChoiceOption[];
  placeholder: string;
  description?: ReactNode;
  required?: boolean;
  disabled?: boolean;
  onChange: (value: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const shown = options.find((o) => o.value === value)?.label ?? '';
  const name = title ?? (typeof label === 'string' ? label : 'Выберите');
  const close = () => setOpen(false);
  return (
    <>
      <Form.Item
        label={label}
        required={required}
        clickable={!disabled}
        arrow={!disabled}
        description={description}
        onClick={disabled ? undefined : () => setOpen(true)}
        style={{ cursor: disabled ? 'default' : 'pointer' }}
      >
        <PickerValue value={shown} placeholder={placeholder} />
      </Form.Item>
      <Popup visible={open} onMaskClick={close} position="bottom" closeOnSwipe bodyStyle={{ background: 'transparent' }}>
        <DraggableSheetBody visible={open} onClose={close} maxHeight="75vh" label={name}>
          <h2 className="choice-sheet__title">{name}</h2>
          <ChoiceList
            options={options}
            value={value}
            onPick={(next) => {
              hapticFeedback('light');
              onChange(next);
              close();
            }}
          />
        </DraggableSheetBody>
      </Popup>
    </>
  );
}
