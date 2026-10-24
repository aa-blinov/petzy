import { useState, useRef, type Ref } from 'react';
import { showToast } from '../utils/toast';
import { useFormContext, Controller } from 'react-hook-form';
import { Input, TextArea, Picker, Form } from 'antd-mobile';
import type { InputRef, TextAreaRef } from 'antd-mobile';
import type { FormField as FormFieldType } from '../utils/formsConfig';
import { getCurrentDate, getCurrentTime, parseDateTime } from '../utils/dateUtils';
import { fieldNote } from './FieldNote';
import { PickerValue } from './PickerValue';
import { DatePickerField } from './DatePickerField';

interface FormFieldProps {
  field: FormFieldType;
  defaultValue?: string;
  /** The cursor starts here (the one thing a new record asks for, with the keyboard already open). */
  autoFocus?: boolean;
  /** A date field only: told whenever the digits typed into it are not a date the form can take (see useTypedDateProblems). */
  onTypedProblem?: (message: string) => void;
  /** A date field only: the form refused to save, so an unfinished typed date shows its message now. */
  refusals?: number;
}

export function FormField({ field, defaultValue, autoFocus, onTypedProblem, refusals }: FormFieldProps) {
  const { control, getValues } = useFormContext();
  const [pickerVisible, setPickerVisible] = useState(false);
  const [internalPickerDate, setInternalPickerDate] = useState<string[]>([]);
  const inputRef = useRef<InputRef | TextAreaRef | null>(null);

  // Use provided defaultValue or fallback to first option for select
  const defaultVal = defaultValue || (field.options && field.options.length > 0 ? field.options[0].value : '');

  // Generate time columns dynamically (restricted if date is today)
  const getTimeColumns = (dateValue: string, currentTimeSelection: string[]) => {
    const now = new Date();
    const isToday = (dateValue || getCurrentDate()) === getCurrentDate();

    const currentHour = now.getHours();
    const currentMinute = now.getMinutes();

    const hours = Array.from({ length: 24 }, (_, i) => ({
      label: i.toString().padStart(2, '0'),
      value: i.toString().padStart(2, '0'),
    })).filter(h => !isToday || parseInt(h.value) <= currentHour);

    const selectedHour = currentTimeSelection.length > 0 ? parseInt(currentTimeSelection[0]) : -1;

    const minutes = Array.from({ length: 60 }, (_, i) => ({
      label: i.toString().padStart(2, '0'),
      value: i.toString().padStart(2, '0'),
    })).filter(m => !isToday || selectedHour < currentHour || parseInt(m.value) <= currentMinute);

    return [hours, minutes];
  };

  const handleRowClick = () => {
    if (field.type === 'time') {
      const currentVal = getValues(field.name) || defaultValue || getCurrentTime();
      setInternalPickerDate(currentVal.split(':'));
      setPickerVisible(true);
    } else if (field.type === 'select') {
      setPickerVisible(true);
    } else if (inputRef.current) {
      inputRef.current.focus();
    }
  };

  return (
    <Controller
      name={field.name}
      control={control}
      render={({ field: { value, onChange, onBlur }, fieldState: { error } }) => {
        // A date is the same control as every other date of the app: the wheel, and «Ввести цифрами» for a date that is far
        // back. The quick choices of the feed form («Сейчас», «Вчера в это время») sit above it and set date and time together.
        if (field.type === 'date') {
          return (
            <DatePickerField
              id={field.name}
              label={field.label}
              required={field.required}
              value={value ?? ''}
              placeholder="Выберите"
              yearsBack={10}
              onChange={(next) => {
                // Not in the future: what the wheel here never offered, and the typed or wheeled date of this year may reach.
                const today = getCurrentDate();
                if (next > today) {
                  showToast.failure('Дата не может быть в будущем');
                  onChange(today);
                } else {
                  onChange(next);
                }
              }}
              onBlur={onBlur}
              onTypedProblem={onTypedProblem}
              refusals={refusals}
              description={fieldNote({ error: error ? (error.message as string) : undefined })}
            />
          );
        }
        const renderInput = () => {
          switch (field.type) {
            case 'time': {
              const timeValue = value ? value.split(':') : (defaultValue ? defaultValue.split(':') : []);
              const displayTime = value || '';
              const currentDateForTime = getValues('date');
              const currentTimeSelection = internalPickerDate.length === 2 ? internalPickerDate : timeValue;

              return (
                <>
                  <PickerValue id={field.name} value={displayTime} placeholder="Выберите" />
                  <Picker
                    columns={getTimeColumns(currentDateForTime, currentTimeSelection)}
                    visible={pickerVisible}
                    onClose={() => {
                      setPickerVisible(false);
                      setInternalPickerDate([]);
                    }}
                    value={currentTimeSelection}
                    onSelect={(val) => setInternalPickerDate(val as string[])}
                    onConfirm={(val) => {
                      const formattedTime = `${String(val[0] || '00')}:${String(val[1] || '00')}`;

                      const now = new Date();
                      const currentDate = getValues('date') || getCurrentDate();
                      const selectedDateTime = parseDateTime(currentDate, formattedTime);

                      if (selectedDateTime > now) {
                        showToast.failure('Время не может быть в будущем');
                        if (currentDate === getCurrentDate()) {
                          onChange(getCurrentTime());
                        } else {
                          onChange(formattedTime);
                        }
                      } else {
                        onChange(formattedTime);
                      }

                      setPickerVisible(false);
                    }}
                    cancelText="Отмена"
                    confirmText="Готово"
                  />
                </>
              );
            }

            case 'select': {
              const options = field.options?.map(opt => ({
                label: opt.text,
                value: opt.value,
              })) || [];
              // Only what is really chosen. Drawing the first option when the
              // value is empty made the row look filled while the form kept an
              // empty value, and the save then refused it («Заполните это поле»)
              // under a row that showed an answer. A field with nothing chosen
              // now says so; the form puts the first option into the value for
              // a required choice, so the row shows it as chosen because it is.
              const selectedOption = options.find(opt => String(opt.value) === String(value));
              return (
                <>
                  <PickerValue id={field.name} value={selectedOption?.label} placeholder="Выберите" />
                  {value !== '' && value !== undefined && value === defaultVal && (
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--app-text-secondary)', marginTop: '4px', fontStyle: 'italic', textAlign: 'left' }}>
                      Значение по умолчанию
                    </div>
                  )}
                  <Picker
                    columns={[options]}
                    visible={pickerVisible}
                    onClose={() => setPickerVisible(false)}
                    value={value ? [String(value)] : []}
                    onConfirm={(val) => {
                      onChange(val[0] ? String(val[0]) : '');
                      setPickerVisible(false);
                    }}
                    cancelText="Отмена"
                    confirmText="Готово"
                  />
                </>
              );
            }

            case 'textarea':
              return (
                <TextArea
                  ref={inputRef as Ref<TextAreaRef>}
                  id={field.name}
                  value={value !== undefined && value !== null ? String(value) : ''}
                  onChange={onChange}
                  onBlur={onBlur}
                  placeholder={field.placeholder}
                  // The server keeps 500 characters of a comment or a text field.
                  maxLength={500}
                  rows={field.rows || 2}
                  style={{ minHeight: '80px' }}
                />
              );

            default: {
              const displayValue = value !== undefined && value !== null ? String(value) : '';
              return (
                <Input
                  ref={inputRef as Ref<InputRef>}
                  type={field.type === 'number' ? 'text' : field.type}
                  inputMode={field.type === 'number' ? 'decimal' : undefined}
                  id={field.name}
                  autoFocus={autoFocus}
                  value={displayValue}
                  onChange={onChange}
                  onBlur={onBlur}
                  placeholder={field.placeholder}
                  maxLength={field.type === 'number' ? undefined : 500}
                  step={field.step}
                  min={field.min}
                  max={field.max}
                />
              );
            }
          }
        };

        return (
          <Form.Item
            clickable
            onClick={handleRowClick}
            arrow={['time', 'select'].includes(field.type)}
            label={field.label}
            required={field.required}
            layout={field.type === 'textarea' ? 'vertical' : undefined}
            style={{
              width: '100%',
              cursor: 'pointer'
            }}
            description={fieldNote({
              error: error ? (error.message as string) : undefined,
              // The server keeps 500 characters of a comment or a text field.
              value: field.type === 'textarea' || field.type === 'text' ? String(value ?? '') : undefined,
              max: field.type === 'textarea' || field.type === 'text' ? 500 : undefined,
              always: field.type === 'textarea',
            })}
          >
            {renderInput()}
          </Form.Item>
        );
      }}
    />
  );
}
