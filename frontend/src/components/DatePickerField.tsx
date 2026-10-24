import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Form, Input, Picker } from 'antd-mobile';
import './DatePickerField.css';
import { ChoiceChip,ChoiceChips } from './ChoiceChips';
import { FieldError } from './FieldError';
import { PickerValue } from './PickerValue';
import { formatTyped, readTypedDate } from '../utils/typedDate';

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
  /** «Сегодня», «Вчера» and «Цифрами» under the field: a recent date is a tap, an old one (the paper passport) is typed
      instead of wheeled to. Only for dates that are not in the future. */
  quick?: boolean;
  /** «Ввести цифрами» under the field: any date can be typed instead of wheeled to, in the past or the future alike, as far
      as the years allow. On unless switched off. */
  typeable?: boolean;
  /** Choices of the field's own (a repeat in a month, in a year), in the same row as «Ввести цифрами»: the field, its
      choices and its typed value are one block. */
  chips?: ReactNode;
  /** Told whenever what is typed is not a date the form can take (empty string: nothing wrong). The form then refuses to
      save instead of silently keeping the older date. */
  onTypedProblem?: (message: string) => void;
  /** The form refused to save: an unfinished typed date shows its message now, not only after a wrong last digit. */
  refusals?: number;
  /** A star by the label: the field must be filled. */
  required?: boolean;
}

const toIso = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

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
  quick = false,
  typeable = true,
  chips,
  onTypedProblem,
  refusals = 0,
  required,
}: DatePickerFieldProps) {
  const [visible, setVisible] = useState(false);
  const [typing, setTyping] = useState(false);
  const [typed, setTyped] = useState('');
  const [typedError, setTypedError] = useState('');
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

  const todayIso = toIso(today);
  const yesterdayIso = toIso(new Date(today.getFullYear(), today.getMonth(), today.getDate() - 1));

  const limits = { today, yearsBack, yearsForward };
  const problemOf = (text: string) => readTypedDate(text, limits).error;
  const report = (text: string, on: boolean) => onTypedProblem?.(on ? problemOf(text) : '');
  const typeIn = (raw: string) => {
    const text = formatTyped(raw);
    setTyped(text);
    const result = readTypedDate(text, limits);
    // An unfinished text is not an error yet (the person is still typing): it is reported to the form, which refuses to save.
    setTypedError(text.length >= 10 ? result.error : '');
    onTypedProblem?.(result.error);
    if (result.iso) {
      onChange(result.iso);
      onBlur?.();
      setTyping(false);
      setTyped('');
    }
  };
  const incomplete = typing && typed.length > 0 && typed.length < 10 && refusals > 0 ? problemOf(typed) : '';
  const shownProblem = typedError || incomplete;
  // A refused save brings the field with the unfinished date into view: the button that was pressed is far below it.
  const groupRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (refusals > 0 && typing && typed) groupRef.current?.scrollIntoView?.({ block: 'center', behavior: 'smooth' });
    // Only a new refusal scrolls; typing on afterwards must not.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refusals]);
  const stopTyping = () => {
    setTyping(false);
    setTyped('');
    setTypedError('');
    report('', false);
  };

  const canClear = !!clearLabel && !!value;
  const chipRow = quick || typeable || !!chips || canClear;

  return (
    <div className="datefield-group" ref={groupRef}>
    <div className="datefield">
    <Form.Item
      label={label}
      required={required}
      clickable
      arrow
      description={description}
      onClick={() => {
        setDraft([]);
        setVisible(true);
      }}
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
          stopTyping();
        }}
        cancelText="Отмена"
        confirmText="Готово"
      />
    </Form.Item>
    </div>
    {chipRow && (
      <Form.Item>
        <ChoiceChips label={`${label}: быстрый выбор`}>
          {quick && (
            <>
              <ChoiceChip pressed={value === todayIso} onClick={() => { onChange(todayIso); onBlur?.(); stopTyping(); }}>Сегодня</ChoiceChip>
              <ChoiceChip pressed={value === yesterdayIso} onClick={() => { onChange(yesterdayIso); onBlur?.(); stopTyping(); }}>Вчера</ChoiceChip>
            </>
          )}
          {chips}
          {/* «Убрать» is an action in the row of choices, not a button laid over the value: at 320px the value, the arrow and
              a word on one line did not fit, and the hint beside them was squeezed into a column of a few letters. */}
          {canClear && (
            <button
              type="button"
              className="choice-chip"
              aria-label={clearLabel}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => { onChange(''); onBlur?.(); stopTyping(); }}
            >
              Убрать
            </button>
          )}
          {typeable && (
            <ChoiceChip pressed={typing} onClick={() => { setTyping((on) => !on); setTyped(''); setTypedError(''); report('', false); }}>Ввести цифрами</ChoiceChip>
          )}
        </ChoiceChips>
      </Form.Item>
    )}
    {typeable && typing && (
      <Form.Item label="Дата цифрами" description={shownProblem ? <FieldError message={shownProblem} /> : 'День, месяц и год подряд, точки поставятся сами'}>
        <Input
          aria-label={`${label}, цифрами`}
          value={typed}
          onChange={typeIn}
          inputMode="numeric"
          enterKeyHint="done"
          placeholder="ДД.ММ.ГГГГ"
          maxLength={10}
          autoFocus
        />
      </Form.Item>
    )}
    </div>
  );
}
