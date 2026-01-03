import { useState } from 'react';
import { Card, Button, Toast, Dialog, Form, Input, DatePicker, Picker, TextArea } from 'antd-mobile';
import { useQueryClient } from '@tanstack/react-query';
import type { HistoryItem as HistoryItemType, HistoryTypeConfig } from '../utils/historyConfig';
import { formatDateTime } from '../utils/historyConfig';
import { healthRecordsService } from '../services/healthRecords.service';
import type { HealthRecordType } from '../utils/constants';
import { formConfigs } from '../utils/formsConfig';

interface HistoryItemProps {
  item: HistoryItemType;
  config: HistoryTypeConfig;
  type: string;
}

// Пастельные цвета для карточек истории (соответствуют дашборду)
const pastelColorMap: Record<string, string> = {
  brown: '#E8D5C4',
  orange: '#FFE5B4',
  red: '#FFD1CC',
  green: '#D4F4DD',
  purple: '#E8D5F2',
  teal: '#D4F4F1',
  cyan: '#D4F0FF',
  yellow: '#FFF9D4',
  blue: '#D4E8FF',
  pink: '#FFE5EB',
};

export function HistoryItem({ item, config, type }: HistoryItemProps) {
  const queryClient = useQueryClient();
  const backgroundColor = pastelColorMap[config.color] || '#D4E8FF';
  const [editVisible, setEditVisible] = useState(false);
  const [loading, setLoading] = useState(false);
  const [pickerVisible, setPickerVisible] = useState<string | null>(null);
  const [form] = Form.useForm();
  const formConfig = formConfigs[type as HealthRecordType];

  const handleEdit = () => {
    // Parse date_time to date and time
    const dateTime = new Date(item.date_time);
    const dateStr = dateTime.toISOString().split('T')[0];
    const timeStr = dateTime.toTimeString().split(' ')[0].substring(0, 5);

    // Prepare form values
    const formValues: any = {
      date: new Date(dateStr),
      time: timeStr,
    };

    // Populate other fields based on item data
    formConfig.fields.forEach(field => {
      if (field.name !== 'date' && field.name !== 'time' && item[field.name] !== undefined) {
        formValues[field.name] = item[field.name];
      }
    });

    form.setFieldsValue(formValues);
    setEditVisible(true);
  };

  const handleSave = async () => {
    try {
      await form.validateFields();
      const values = form.getFieldsValue();
      setLoading(true);

      // Transform form data
      const dateStr = values.date instanceof Date 
        ? values.date.toISOString().split('T')[0]
        : values.date;

      const updateData: any = {
        date: dateStr,
        time: values.time,
      };

      // Add other fields
      formConfig.fields.forEach(field => {
        if (field.name !== 'date' && field.name !== 'time' && values[field.name] !== undefined) {
          updateData[field.name] = values[field.name];
        }
      });

      await healthRecordsService.update(type as HealthRecordType, item._id, updateData);
      await queryClient.invalidateQueries({ queryKey: ['history'] });
      Toast.show({ content: formConfig.successMessage(true), icon: 'success' });
      setEditVisible(false);
    } catch (error: any) {
      if (error?.errorFields) {
        // Form validation error
        return;
      }
      console.error('Error updating record:', error);
      Toast.show({ content: 'Ошибка при сохранении', icon: 'fail' });
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    const confirmed = window.confirm('Вы уверены, что хотите удалить эту запись?');
    if (confirmed) {
      try {
        await healthRecordsService.delete(type as HealthRecordType, item._id);
        await queryClient.invalidateQueries({ queryKey: ['history'] });
        Toast.show({ content: 'Запись удалена', icon: 'success' });
      } catch (error) {
        console.error('Error deleting record:', error);
        Toast.show({ content: 'Ошибка при удалении', icon: 'fail' });
      }
    }
  };

  const renderFormField = (field: typeof formConfig.fields[0]) => {
    switch (field.type) {
      case 'date':
        return (
          <Form.Item
            key={field.name}
            name={field.name}
            label={field.label}
            rules={[{ required: field.required, message: `${field.label} обязательно` }]}
          >
            <DatePicker max={new Date()}>
              {(value) => value ? value.toLocaleDateString('ru-RU') : 'Выберите дату'}
            </DatePicker>
          </Form.Item>
        );

      case 'time':
        return (
          <Form.Item
            key={field.name}
            name={field.name}
            label={field.label}
            rules={[{ required: field.required, message: `${field.label} обязательно` }]}
          >
            <Input type="time" placeholder={field.placeholder} />
          </Form.Item>
        );

      case 'number':
        return (
          <Form.Item
            key={field.name}
            name={field.name}
            label={field.label}
            rules={[{ required: field.required, message: `${field.label} обязательно` }]}
          >
            <Input 
              type="number" 
              placeholder={field.placeholder}
              min={field.min}
              max={field.max}
              step={field.step}
            />
          </Form.Item>
        );

      case 'select':
        const options = field.options?.map(opt => ({ label: opt.text, value: opt.value })) || [];
        const currentValue = form.getFieldValue(field.name);
        const selectedOption = options.find(opt => opt.value === currentValue);
        return (
          <>
            <Form.Item
              key={field.name}
              name={field.name}
              label={field.label}
              rules={[{ required: field.required, message: `${field.label} обязательно` }]}
              onClick={() => setPickerVisible(field.name)}
              arrow
            >
              {selectedOption?.label || 'Выберите...'}
            </Form.Item>
            <Picker
              columns={[options]}
              visible={pickerVisible === field.name}
              onClose={() => setPickerVisible(null)}
              value={currentValue ? [currentValue] : []}
              onConfirm={(val) => {
                form.setFieldValue(field.name, val[0] as string || '');
                setPickerVisible(null);
              }}
              cancelText="Отмена"
              confirmText="Сохранить"
            />
          </>
        );

      case 'textarea':
        return (
          <Form.Item
            key={field.name}
            name={field.name}
            label={field.label}
          >
            <TextArea 
              placeholder={field.placeholder}
              rows={field.rows || 3}
            />
          </Form.Item>
        );

      case 'text':
      default:
        return (
          <Form.Item
            key={field.name}
            name={field.name}
            label={field.label}
            rules={[{ required: field.required, message: `${field.label} обязательно` }]}
          >
            <Input placeholder={field.placeholder} />
          </Form.Item>
        );
    }
  };

  return (
    <>
      <Card
        style={{
          backgroundColor: backgroundColor,
          borderRadius: '12px',
          border: 'none',
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
        }}
      >
        <div style={{ padding: '16px' }}>
          <div style={{ 
            color: '#000000', 
            fontWeight: 500, 
            marginBottom: '8px', 
            fontSize: '16px' 
          }}>
            {formatDateTime(item.date_time)}
          </div>
          {item.username && (
            <div style={{ color: '#666666', fontSize: '14px', marginBottom: '12px' }}>
              <strong>Пользователь:</strong> {item.username}
            </div>
          )}
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '8px',
              marginBottom: '16px',
              color: '#000000',
            }}
            dangerouslySetInnerHTML={{ __html: config.renderDetails(item) }}
          />
          <div style={{ display: 'flex', gap: '8px', marginTop: '16px' }}>
            <Button
              size="small"
              fill="outline"
              onClick={handleEdit}
              style={{
                '--text-color': '#000000',
                '--border-color': 'rgba(0, 0, 0, 0.15)',
              } as React.CSSProperties}
            >
              Редактировать
            </Button>
            <Button
              size="small"
              fill="outline"
              onClick={handleDelete}
              style={{
                '--text-color': '#FF453A',
                '--border-color': 'rgba(255, 69, 58, 0.3)',
              } as React.CSSProperties}
            >
              Удалить
            </Button>
          </div>
        </div>
      </Card>

      {/* Edit Modal */}
      <Dialog
        visible={editVisible}
        onClose={() => setEditVisible(false)}
        title={formConfig.title}
        content={
          <Form
            form={form}
            layout="vertical"
            footer={
              <div style={{ display: 'flex', gap: '8px' }}>
                <Button 
                  onClick={() => setEditVisible(false)}
                  style={{ flex: 1 }}
                >
                  Отмена
                </Button>
                <Button 
                  color="primary" 
                  onClick={handleSave} 
                  loading={loading}
                  style={{ flex: 1 }}
                >
                  Сохранить
                </Button>
              </div>
            }
          >
            {formConfig.fields.map(field => renderFormField(field))}
          </Form>
        }
      />
    </>
  );
}
