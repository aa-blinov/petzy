import { useState, useMemo } from 'react';
import { useFormContext } from 'react-hook-form';
import { Input, TextArea, Picker, Form } from 'antd-mobile';
import { RightOutline } from 'antd-mobile-icons';
import type { FormField as FormFieldType } from '../utils/formsConfig';

interface FormFieldProps {
  field: FormFieldType;
  defaultValue?: string;
}

export function FormField({ field, defaultValue }: FormFieldProps) {
  const { formState: { errors }, setValue, watch } = useFormContext();
  const error = errors?.[field.name];
  const isHalfWidth = field.name === 'date' || field.name === 'time';
  const value = watch(field.name);
  const [pickerVisible, setPickerVisible] = useState(false);
  const [datePickerVisible, setDatePickerVisible] = useState(false);
  
  // Internal state for date picker to calculate dynamic days while scrolling
  const [internalPickerDate, setInternalPickerDate] = useState<string[]>([]);
  
  // Use provided defaultValue or fallback to first option
  const defaultVal = defaultValue || (field.options && field.options.length > 0 ? field.options[0].value : '');

  // Generate time columns for Picker (HH:MM)
  const timeColumns = useMemo(() => {
    const hours = Array.from({ length: 24 }, (_, i) => ({
      label: i.toString().padStart(2, '0'),
      value: i.toString().padStart(2, '0'),
    }));
    const minutes = Array.from({ length: 60 }, (_, i) => ({
      label: i.toString().padStart(2, '0'),
      value: i.toString().padStart(2, '0'),
    }));
    return [hours, minutes];
  }, []);

  // Generate date columns dynamically [Day, Month, Year]
  const dateColumns = useMemo(() => {
    // Determine which month and year to use for day calculation
    let month = new Date().getMonth();
    let year = new Date().getFullYear();

    if (internalPickerDate.length === 3) {
      month = parseInt(internalPickerDate[1]);
      year = parseInt(internalPickerDate[2]);
    } else if (value) {
      const d = new Date(value);
      if (!isNaN(d.getTime())) {
        month = d.getMonth();
        year = d.getFullYear();
      }
    }

    // Get days in current selected month/year
    const daysCount = new Date(year, month + 1, 0).getDate();

    const days = Array.from({ length: daysCount }, (_, i) => ({
      label: String(i + 1).padStart(2, '0'),
      value: String(i + 1),
    }));
    
    const months = [
      'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
      'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
    ].map((m, i) => ({ label: m, value: String(i) }));

    const currentYear = new Date().getFullYear();
    const years = Array.from({ length: 21 }, (_, i) => {
      const y = currentYear - 10 + i;
      return { label: String(y), value: String(y) };
    });

    return [days, months, years];
  }, [internalPickerDate, value]);
  
  const renderInput = () => {
    switch (field.type) {
      case 'date':
        // Initial value for the picker drums
        let pickerValue: string[] = [];
        if (value) {
          const d = new Date(value);
          pickerValue = [String(d.getDate()), String(d.getMonth()), String(d.getFullYear())];
        } else {
          const now = new Date();
          pickerValue = [String(now.getDate()), String(now.getMonth()), String(now.getFullYear())];
        }

        const displayDate = value ? new Date(value).toLocaleDateString('ru-RU') : 'Выберите дату';
        
        return (
          <>
            <div 
              onClick={() => {
                setInternalPickerDate(pickerValue);
                setDatePickerVisible(true);
              }}
              style={{ 
                padding: '8px 0',
                cursor: 'pointer',
                color: 'var(--adm-color-text)',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                justifyContent: 'flex-start'
              }}
            >
              <span>{displayDate}</span>
              <RightOutline style={{ color: 'var(--adm-color-weak)', fontSize: '14px' }} />
            </div>
            <Picker
              columns={dateColumns}
              visible={datePickerVisible}
              onClose={() => setDatePickerVisible(false)}
              value={internalPickerDate.length ? internalPickerDate : pickerValue}
              onSelect={(val) => {
                setInternalPickerDate(val as string[]);
              }}
              onConfirm={(val) => {
                const day = val[0];
                const month = parseInt(val[1] as string);
                const year = val[2];
                
                const monthStr = String(month + 1).padStart(2, '0');
                const dayStr = String(day).padStart(2, '0');
                const formattedDate = `${year}-${monthStr}-${dayStr}`;
                
                setValue(field.name, formattedDate, { shouldValidate: true });
                setDatePickerVisible(false);
                setInternalPickerDate([]); // Clear temp state
              }}
              cancelText="Отмена"
              confirmText="Сохранить"
            />
          </>
        );

      case 'time':
        const timeValue = value ? value.split(':') : (defaultValue ? defaultValue.split(':') : []);
        const displayTime = value || 'Выберите время';

        return (
          <>
            <div 
              onClick={() => setPickerVisible(true)}
              style={{ 
                padding: '8px 0',
                cursor: 'pointer',
                color: 'var(--adm-color-text)',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                justifyContent: 'flex-start'
              }}
            >
              <span>{displayTime}</span>
              <RightOutline style={{ color: 'var(--adm-color-weak)', fontSize: '14px' }} />
            </div>
            <Picker
              columns={timeColumns}
              visible={pickerVisible}
              onClose={() => setPickerVisible(false)}
              value={timeValue}
              onConfirm={(val) => {
                const formattedTime = `${String(val[0] || '00')}:${String(val[1] || '00')}`;
                setValue(field.name, formattedTime, { shouldValidate: true });
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
        const selectedOption = options.find(opt => opt.value === value) || options[0];
        return (
          <>
            <div 
              onClick={() => setPickerVisible(true)}
              style={{ 
                padding: '8px 0',
                cursor: 'pointer',
                color: 'var(--adm-color-text)',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                justifyContent: 'flex-start'
              }}
            >
              <span>{selectedOption?.label || 'Выберите...'}</span>
              <RightOutline style={{ color: 'var(--adm-color-weak)', fontSize: '14px' }} />
            </div>
            {value === defaultVal && (
              <div style={{ 
                fontSize: '12px', 
                color: '#666666', 
                marginTop: '4px',
                fontStyle: 'italic'
              }}>
                Значение по умолчанию
              </div>
            )}
            <Picker
              columns={[options]}
              visible={pickerVisible}
              onClose={() => setPickerVisible(false)}
              value={value ? [value] : []}
              onConfirm={(val) => {
                setValue(field.name, val[0] as string || '', { shouldValidate: true });
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
            id={field.id}
            value={value || ''}
            onChange={(val) => {
              setValue(field.name, val, { shouldValidate: true });
            }}
            placeholder={field.placeholder}
            rows={field.rows || 2}
            style={{ minHeight: '80px' }}
          />
        );

      default:
        // For number fields, ensure we display the value correctly
        const displayValue = field.type === 'number' 
          ? (value !== undefined && value !== null && value !== '' ? String(value) : '')
          : (value || '');

        return (
          <Input
            type={field.type}
            id={field.id}
            value={displayValue}
            onChange={(val) => {
              if (field.type === 'number') {
                const numValue = val === '' ? undefined : parseFloat(val);
                setValue(field.name, isNaN(numValue as number) ? undefined : numValue, { shouldValidate: true });
              } else {
                setValue(field.name, val, { shouldValidate: true });
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
      label={field.label + (field.required ? ' *' : '')}
      name={field.name}
      style={{ 
        width: isHalfWidth ? '100%' : '100%',
        marginBottom: '16px'
      }}
      help={error ? (error.message as string) : undefined}
    >
      {renderInput()}
    </Form.Item>
  );
}

