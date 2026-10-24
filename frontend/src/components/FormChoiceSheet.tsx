import { Popup } from 'antd-mobile';
import { Check } from 'lucide-react';

import { DraggableSheetBody } from './DraggableSheetBody';
import './FormChoiceSheet.css';

export interface FormChoiceOption {
  value: string;
  label: string;
}

/**
 * A fixed list in a sheet: a tap on a line chooses it and closes the sheet. There is no «Готово», so nobody accepts the
 * first line without having looked. The wheel stays for what is a number or a moment (a date, a time); a list of names is
 * read, not spun.
 */
export function FormChoiceSheet({
  visible,
  title,
  options,
  value,
  onClose,
  onSelect,
}: {
  visible: boolean;
  title: string;
  options: FormChoiceOption[];
  /** The line that is chosen now, marked in the list. */
  value?: string;
  onClose: () => void;
  onSelect: (value: string) => void;
}) {
  return (
    <Popup visible={visible} onMaskClick={onClose} position="bottom" bodyStyle={{ background: 'transparent' }}>
      <DraggableSheetBody visible={visible} onClose={onClose} maxHeight="85vh" label={title}>
        <h2 className="choice-sheet__title">{title}</h2>
        <ul className="choice-sheet__list">
          {options.map((option) => {
            const chosen = option.value === value;
            return (
              <li key={option.value}>
                <button
                  type="button"
                  className={`choice-sheet__row tap-feedback${chosen ? ' choice-sheet__row--chosen' : ''}`}
                  aria-current={chosen ? 'true' : undefined}
                  onClick={() => onSelect(option.value)}
                >
                  <span>{option.label}</span>
                  {chosen && <Check size={18} strokeWidth={2.4} aria-hidden />}
                </button>
              </li>
            );
          })}
        </ul>
      </DraggableSheetBody>
    </Popup>
  );
}
