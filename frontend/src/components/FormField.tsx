import { useState, useRef, type Ref } from 'react';
import { parseRecordDate } from '../utils/relativeTime';
import { showToast } from '../utils/toast';
import { useFormContext, Controller } from 'react-hook-form';
import { Input, TextArea, Picker, Form } from 'antd-mobile';
import type { InputRef, TextAreaRef } from 'antd-mobile';
import type { FormField as FormFieldType } from '../utils/formsConfig';
import { getCurrentDate, getCurrentTime, parseDateTime } from '../utils/dateUtils';
import { FieldError } from './FieldError';

interface FormFieldProps {
  field: FormFieldType;
  defaultValue?: string;
}

export function FormField({ field, defaultValue }: FormFieldProps) {
  const { control, getValues } = useFormContext();
  const [pickerVisible, setPickerVisible] = useState(false);
  const [datePickerVisible, setDatePickerVisible] = useState(false);
  const [internalPickerDate, setInternalPickerDate] = useState<string[]>([]);
  const inputRef = useRef<InputRef | TextAreaRef | null>(null);

  // Use provided defaultValue or fallback to first option for select
  const defaultVal = defaultValue || (field.options && field.options.length > 0 ? field.options[0].value : '');

  // Generate date columns dynamically [Day, Month, Year]
  const dateColumns = (currentValue: string) => {
    const now = new Date();
    const currentYear = now.getFullYear();
    const currentMonth = now.getMonth();
    const currentDay = now.getDate();

    let selectedMonth = now.getMonth();
    let selectedYear = now.getFullYear();

    if (internalPickerDate.length === 3) {
      selectedMonth = parseInt(internalPickerDate[1]);
      selectedYear = parseInt(internalPickerDate[2]);
    } else if (currentValue) {
      // Form date values are "YYYY-MM-DD". new Date() reads that as ISO,
      // i.e. UTC midnight, and the local getters below then report the
      // previous day for anyone west of UTC.
      const d = parseRecordDate(currentValue);
      if (d) {
        selectedMonth = d.getMonth();
        selectedYear = d.getFullYear();
      }
    }

    // Years: from 10 years ago up to current year
    const years = Array.from({ length: 11 }, (_, i) => {
      const y = currentYear - 10 + i;
      return { label: String(y), value: String(y) };
    });

    // Months: if current year, only up to current month
    const monthNames = [
      'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
      'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
    ];
    const months = monthNames
      .map((m, i) => ({ label: m, value: String(i) }))
      .filter(m => selectedYear < currentYear || parseInt(m.value) <= currentMonth);

    // Days: if current year and month, only up to current day
    const daysCount = new Date(selectedYear, selectedMonth + 1, 0).getDate();
    const days = Array.from({ length: daysCount }, (_, i) => ({
      label: String(i + 1).padStart(2, '0'),
      value: String(i + 1),
    })).filter(d =>
      selectedYear < currentYear ||
      selectedMonth < currentMonth ||
      parseInt(d.value) <= currentDay
    );

    return [days, months, years];
  };

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
    if (field.type === 'date') {
      const currentVal = getValues(field.name);
      let pValue: string[] = [];
      if (currentVal) {
        const d = parseRecordDate(currentVal) ?? new Date();
        pValue = [String(d.getDate()), String(d.getMonth()), String(d.getFullYear())];
      } else {
        const now = new Date();
        pValue = [String(now.getDate()), String(now.getMonth()), String(now.getFullYear())];
      }
      setInternalPickerDate(pValue);
      setDatePickerVisible(true);
    } else if (field.type === 'time') {
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
      render={({ field: { value, onChange }, fieldState: { error } }) => {
        const renderInput = () => {
          switch (field.type) {
            case 'date': {
              const displayDate = value
                ? (parseRecordDate(value)?.toLocaleDateString('ru-RU') ?? value)
                : '';

              return (
                <>
                  <Input
                    ref={inputRef as Ref<InputRef>}
                    id={field.name}
                    readOnly
                    value={displayDate}
                    placeholder="Выберите дату"
                  />
                  <Picker
                    columns={dateColumns(value)}
                    visible={datePickerVisible}
                    onClose={() => setDatePickerVisible(false)}
                    value={internalPickerDate.length ? internalPickerDate : []}
                    onSelect={(val) => setInternalPickerDate(val as string[])}
                    onConfirm={(val) => {
                      const day = val[0];
                      const month = parseInt(val[1] as string);
                      const year = parseInt(val[2] as string);
                      const monthStr = String(month + 1).padStart(2, '0');
                      const dayStr = String(day).padStart(2, '0');
                      const formattedDate = `${year}-${monthStr}-${dayStr}`;

                      const todayStr = getCurrentDate();
                      if (formattedDate > todayStr) {
                        showToast.failure('Дата не может быть в будущем');
                        onChange(todayStr);
                      } else {
                        onChange(formattedDate);
                      }

                      setDatePickerVisible(false);
                      setInternalPickerDate([]);
                    }}
                    cancelText="Отмена"
                    confirmText="Сохранить"
                  />
                </>
              );
            }

            case 'time': {
              const timeValue = value ? value.split(':') : (defaultValue ? defaultValue.split(':') : []);
              const displayTime = value || '';
              const currentDateForTime = getValues('date');
              const currentTimeSelection = internalPickerDate.length === 2 ? internalPickerDate : timeValue;

              return (
                <>
                  <Input
                    ref={inputRef as Ref<InputRef>}
                    id={field.name}
                    readOnly
                    value={displayTime}
                    placeholder="Выберите время"
                  />
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
                    confirmText="Сохранить"
                  />
                </>
              );
            }

            case 'select': {
              const options = field.options?.map(opt => ({
                label: opt.text,
                value: opt.value,
              })) || [];
              const selectedOption = options.find(opt => String(opt.value) === String(value)) || options[0];
              return (
                <>
                  <Input
                    ref={inputRef as Ref<InputRef>}
                    id={field.name}
                    readOnly
                    value={selectedOption?.label || ''}
                    placeholder="Выберите..."
                  />
                  {value === defaultVal && (
                    <div style={{ fontSize: '12px', color: 'var(--app-text-secondary)', marginTop: '4px', fontStyle: 'italic', textAlign: 'left' }}>
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
                    confirmText="Сохранить"
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
                  placeholder={field.placeholder}
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
                  value={displayValue}
                  onChange={onChange}
                  placeholder={field.placeholder}
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
            arrow={['date', 'time', 'select'].includes(field.type)}
            label={field.label}
            required={field.required}
            layout={field.type === 'textarea' ? 'vertical' : undefined}
            style={{
              width: '100%',
              cursor: 'pointer'
            }}
            description={error ? <FieldError message={error.message as string} /> : undefined}
          >
            {renderInput()}
          </Form.Item>
        );
      }}
    />
  );
}
