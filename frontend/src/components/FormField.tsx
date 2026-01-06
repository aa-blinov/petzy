import { useState } from 'react';
import { useFormContext, Controller } from 'react-hook-form';
import { Input, TextArea, Picker, Form, Toast } from 'antd-mobile';
import type { FormField as FormFieldType } from '../utils/formsConfig';
import { getCurrentDate, getCurrentTime, parseDateTime } from '../utils/dateUtils';

interface FormFieldProps {
  field: FormFieldType;
  defaultValue?: string;
}

export function FormField({ field, defaultValue }: FormFieldProps) {
  const { control, getValues } = useFormContext();
  const [pickerVisible, setPickerVisible] = useState(false);
  const [datePickerVisible, setDatePickerVisible] = useState(false);
  const [internalPickerDate, setInternalPickerDate] = useState<string[]>([]);

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
      const d = new Date(currentValue);
      if (!isNaN(d.getTime())) {
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

  return (
    <Controller
      name={field.name}
      control={control}
      render={({ field: { value, onChange }, fieldState: { error } }) => {
        const renderInput = () => {
          switch (field.type) {
            case 'date':
              let pickerValue: string[] = [];
              if (value) {
                const d = new Date(value);
                pickerValue = [String(d.getDate()), String(d.getMonth()), String(d.getFullYear())];
              } else {
                const now = new Date();
                pickerValue = [String(now.getDate()), String(now.getMonth()), String(now.getFullYear())];
              }
              const displayDate = value ? new Date(value).toLocaleDateString('ru-RU') : '';

              return (
                <>
                  <Input
                    id={field.name}
                    readOnly
                    value={displayDate}
                    placeholder="Выберите дату"
                    onClick={() => {
                      setInternalPickerDate(pickerValue);
                      setDatePickerVisible(true);
                    }}
                    style={{ '--font-size': '16px' }}
                  />
                  <Picker
                    columns={dateColumns(value)}
                    visible={datePickerVisible}
                    onClose={() => setDatePickerVisible(false)}
                    value={internalPickerDate.length ? internalPickerDate : pickerValue}
                    onSelect={(val) => setInternalPickerDate(val as string[])}
                    onConfirm={(val) => {
                      const day = val[0];
                      const month = parseInt(val[1] as string);
                      const year = parseInt(val[2] as string);
                      const monthStr = String(month + 1).padStart(2, '0');
                      const dayStr = String(day).padStart(2, '0');
                      const formattedDate = `${year}-${monthStr}-${dayStr}`;

                      // Prevent future date
                      // Normalize now to start of next day for date-only comparison would be too much, 
                      // but we can just compare the strings or date objects
                      const todayStr = getCurrentDate();
                      if (formattedDate > todayStr) {
                        Toast.show({ content: 'Дата не может быть в будущем', icon: 'fail' });
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

            case 'time':
              const timeValue = value ? value.split(':') : (defaultValue ? defaultValue.split(':') : []);
              const displayTime = value || '';
              const currentDateForTime = getValues('date');
              const currentTimeSelection = internalPickerDate.length === 2 ? internalPickerDate : timeValue;

              return (
                <>
                  <Input
                    id={field.name}
                    readOnly
                    value={displayTime}
                    placeholder="Выберите время"
                    onClick={() => {
                      setInternalPickerDate(timeValue);
                      setPickerVisible(true);
                    }}
                    style={{ '--font-size': '16px' }}
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

                      // Prevent future time if date is today
                      const now = new Date();
                      const currentDate = getValues('date') || getCurrentDate();
                      const selectedDateTime = parseDateTime(currentDate, formattedTime);

                      if (selectedDateTime > now) {
                        Toast.show({ content: 'Время не может быть в будущем', icon: 'fail' });
                        // If it's today, set to current time. If it's a past date (shouldn't happen with future date check), keep it.
                        if (currentDate === getCurrentDate()) {
                          onChange(getCurrentTime());
                        } else {
                          // This case won't be hit because we check date first, but for safety:
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

            case 'select':
              const options = field.options?.map(opt => ({
                label: opt.text,
                value: opt.value,
              })) || [];
              const selectedOption = options.find(opt => String(opt.value) === String(value)) || options[0];
              return (
                <>
                  <Input
                    id={field.name}
                    readOnly
                    value={selectedOption?.label || ''}
                    placeholder="Выберите..."
                    onClick={() => setPickerVisible(true)}
                    style={{ '--font-size': '16px' }}
                  />
                  {value === defaultVal && (
                    <div style={{ fontSize: '12px', color: '#666666', marginTop: '4px', fontStyle: 'italic' }}>
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

            case 'textarea':
              return (
                <TextArea
                  id={field.name}
                  aria-label={field.label}
                  value={value !== undefined && value !== null ? String(value) : ''}
                  onChange={onChange}
                  placeholder={field.placeholder}
                  rows={field.rows || 2}
                  style={{ minHeight: '80px' }}
                />
              );

            default:
              const displayValue = field.type === 'number'
                ? (value !== undefined && value !== null && value !== '' ? String(value) : '')
                : (value !== undefined && value !== null ? String(value) : '');
              return (
                <Input
                  type={field.type}
                  id={field.name}
                  aria-label={field.label}
                  value={displayValue}
                  onChange={(val) => {
                    if (field.type === 'number') {
                      const numValue = val === '' ? undefined : parseFloat(val);
                      onChange(isNaN(numValue as number) ? undefined : numValue);
                    } else {
                      onChange(val);
                    }
                  }}
                  placeholder={field.placeholder}
                  step={field.step}
                  min={field.min}
                  max={field.max}
                />
              );
          }
        };

        return (
          <Form.Item
            label={
              <label htmlFor={field.name} style={{ cursor: 'pointer' }}>
                {field.label}{field.required ? ' *' : ''}
              </label>
            }
            style={{
              width: '100%',
            }}
            help={error ? (error.message as string) : undefined}
          >
            {renderInput()}
          </Form.Item>
        );
      }}
    />
  );
}

