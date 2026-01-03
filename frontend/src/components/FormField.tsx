import { useFormContext } from 'react-hook-form';
import { Input, TextArea, Selector, Form } from 'antd-mobile';
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
  // Use provided defaultValue or fallback to first option
  const defaultVal = defaultValue || (field.options && field.options.length > 0 ? field.options[0].value : '');

  const renderInput = () => {
    switch (field.type) {
      case 'select':
        const options = field.options?.map(opt => ({
          label: opt.text,
          value: opt.value,
        })) || [];
        return (
          <div>
            <Selector
              options={options}
              value={value ? [String(value)] : []}
              onChange={(arr) => {
                setValue(field.name, arr[0] || '', { shouldValidate: true });
              }}
              style={{ width: '100%' }}
            />
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
          </div>
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
        const isDateTime = field.type === 'date' || field.type === 'time';
        return (
          <div style={{ 
            position: 'relative',
            width: '100%',
            overflow: 'visible'
          }}>
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
              style={{ 
                width: '100%',
                paddingRight: isDateTime ? '40px' : undefined,
                boxSizing: 'border-box',
                WebkitAppearance: 'none',
                fontSize: isDateTime ? '16px' : undefined, // Prevent zoom on iOS
              }}
            />
          </div>
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

