import { useMemo, useState, type ReactNode } from 'react';
import { Form, Picker } from 'antd-mobile';
import { PickerValue } from './PickerValue';

const MONTHS = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'];

const pad = (n: number) => String(n).padStart(2, '0');

function parse(value: string): { y: number; m: number; d: number } | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!match) return null;
  return { y: Number(match[1]), m: Number(match[2]) - 1, d: Number(match[3]) };
}

interface DatePickerFieldProps {
  label: string;
  /** `YYYY-MM-DD`, or empty for «not set». */
  value: string;
  onChange: (value: string) => void;
  /** Years offered before and after this year. A date outside them that is already set stays selectable. */
  yearsBack?: number;
  yearsForward?: number;
  placeholder?: string;
  /** Shows «Убрать» while a date is set. */
  clearLabel?: string;
  description?: ReactNode;
  onBlur?: () => void;
  id?: string;
}

/**
 * A row that opens a day, month, year picker: the one for forms that need a
 * date other than a record's own («Начало курса», «Следующая прививка»).
 * Unlike the record form's picker it can reach into the future, as far as
 * the caller says, and the date can be taken away again.
 */
export function DatePickerField({
  label,
  value,
  onChange,
  yearsBack = 10,
  yearsForward = 0,
  placeholder = 'Не указано',
  clearLabel,
  description,
  onBlur,
  id,
}: DatePickerFieldProps) {
  const [visible, setVisible] = useState(false);
  const [draft, setDraft] = useState<string[]>([]);

  const [today] = useState(() => new Date());
  const parsed = useMemo(() => parse(value), [value]);
  const current = useMemo(() => {
    if (draft.length === 3) return draft;
    const from = parsed ?? { y: today.getFullYear(), m: today.getMonth(), d: today.getDate() };
    return [String(from.d), String(from.m), String(from.y)];
  }, [draft, parsed, today]);

  const columns = useMemo(() => {
    const year = Number(current[2]);
    const month = Number(current[1]);
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const days = Array.from({ length: daysInMonth }, (_, i) => ({ label: pad(i + 1), value: String(i + 1) }));
    const months = MONTHS.map((name, i) => ({ label: name, value: String(i) }));
    const thisYear = new Date().getFullYear();
    const first = Math.min(thisYear - yearsBack, parsed?.y ?? thisYear);
    const last = Math.max(thisYear + yearsForward, parsed?.y ?? thisYear);
    const years = Array.from({ length: last - first + 1 }, (_, i) => ({ label: String(first + i), value: String(first + i) }));
    return [days, months, years];
  }, [current, yearsBack, yearsForward, parsed?.y]);

  const shown = parsed ? `${pad(parsed.d)}.${pad(parsed.m + 1)}.${parsed.y}` : '';

  return (
    <Form.Item
      label={label}
      clickable
      arrow
      description={description}
      onClick={() => {
        setDraft([]);
        setVisible(true);
      }}
      extra={
        clearLabel && value ? (
          <button
            type="button"
            aria-label={clearLabel}
            onClick={(event) => {
              event.stopPropagation();
              onChange('');
              onBlur?.();
            }}
            style={{
              padding: '8px 0 8px 8px',
              border: 'none',
              background: 'none',
              color: 'var(--app-accent-deep)',
              fontFamily: 'inherit',
              fontSize: 'var(--text-sm)',
              cursor: 'pointer',
            }}
          >
            Убрать
          </button>
        ) : undefined
      }
    >
      <PickerValue id={id} value={shown} placeholder={placeholder} />
      <Picker
        columns={columns}
        visible={visible}
        onClose={() => {
          setVisible(false);
          onBlur?.();
        }}
        value={current}
        onSelect={(val) => setDraft(val as string[])}
        onConfirm={(val) => {
          const [d, m, y] = val as string[];
          const last = new Date(Number(y), Number(m) + 1, 0).getDate();
          onChange(`${y}-${pad(Number(m) + 1)}-${pad(Math.min(Number(d), last))}`);
          setVisible(false);
          setDraft([]);
        }}
        cancelText="Отмена"
        confirmText="Готово"
      />
    </Form.Item>
  );
}
