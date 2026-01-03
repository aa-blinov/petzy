import { useState } from 'react';
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
  // Use provided defaultValue or fallback to first option
  const defaultVal = defaultValue || (field.options && field.options.length > 0 ? field.options[0].value : '');

  const renderInput = () => {
    switch (field.type) {
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
                justifyContent: 'space-between'
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
        return (
          <Input
            type={field.type}
            id={field.id}
            value={value || ''}
            onChange={(val) => {
              const numValue = field.type === 'number' ? parseFloat(val) || 0 : val;
              setValue(field.name, numValue, { shouldValidate: true });
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

