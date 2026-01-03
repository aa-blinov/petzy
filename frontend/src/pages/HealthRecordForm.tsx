import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useForm, FormProvider } from 'react-hook-form';
import { useQueryClient } from '@tanstack/react-query';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button, Form, SpinLoading, Toast } from 'antd-mobile';
import { usePet } from '../hooks/usePet';
import { formConfigs, getFormSettings } from '../utils/formsConfig';
import type { HealthRecordType } from '../utils/constants';
import { getCurrentDate, getCurrentTime } from '../utils/dateUtils';
import { healthRecordsService } from '../services/healthRecords.service';
import { FormField } from '../components/FormField';

export function HealthRecordForm() {
  const { type, id } = useParams<{ type: HealthRecordType; id?: string }>();
  const navigate = useNavigate();
  const { selectedPetId } = usePet();
  const queryClient = useQueryClient();
  const config = type && type in formConfigs ? formConfigs[type as HealthRecordType] : null;
  const [isLoading, setIsLoading] = useState(!!id);

  if (!type || !config) {
    return <div>Неизвестный тип записи</div>;
  }

  const settings = getFormSettings();
  const defaultValues: Record<string, any> = {
    date: getCurrentDate(),
    time: getCurrentTime(),
    pet_id: selectedPetId || ''
  };

  // Apply default values from settings
  if (!id && type && type in settings && settings[type as keyof typeof settings]) {
    Object.assign(defaultValues, settings[type as keyof typeof settings]);
  }

  // Create Zod schema dynamically
  const schema = z.object(
    config.fields.reduce((acc: Record<string, any>, field: any) => {
      if (field.type === 'number') {
        acc[field.name] = field.required
          ? z.number().min(field.min || 0)
          : z.number().min(field.min || 0).optional();
      } else {
        acc[field.name] = field.required
          ? z.string().min(1)
          : z.string().optional();
      }
      return acc;
    }, {} as Record<string, any>)
  );

  const methods = useForm({
    resolver: zodResolver(schema),
    defaultValues
  });

  const {
    handleSubmit,
    formState: { isSubmitting },
    setValue,
    reset
  } = methods;

  useEffect(() => {
    if (!selectedPetId) {
      navigate('/');
    } else if (!id) {
      setValue('pet_id', selectedPetId);
    }
  }, [selectedPetId, navigate, setValue, id]);

  // Load data if editing
  useEffect(() => {
    if (id && type) {
      setIsLoading(true);
      healthRecordsService.get(type as HealthRecordType, id)
        .then(data => {
          // Prepare form data
          const formData: Record<string, any> = {
            pet_id: data.pet_id,
          };

          // Format date and time
          if (data.date_time) {
            const [datePart, timePart] = data.date_time.split(' ');
            if (datePart && timePart) {
               formData.date = datePart;
               formData.time = timePart;
            }
          }
          
          // Set other fields
          config.fields.forEach((field: any) => {
            if (field.name !== 'date' && field.name !== 'time' && data[field.name] !== undefined) {
              formData[field.name] = data[field.name];
            }
          });
          
          reset(formData);
        })
        .catch(err => {
          console.error('Error loading record:', err);
          Toast.show({ content: 'Ошибка загрузки записи', icon: 'fail' });
          navigate('/history');
        })
        .finally(() => setIsLoading(false));
    }
  }, [id, type, setValue, navigate, config]);

  const onSubmit = async (data: Record<string, any>) => {
    if (!selectedPetId || !type) {
      return;
    }

    try {
      const transformedData = config.transformData({
        ...data,
        pet_id: selectedPetId
      }) as any;

      if (id) {
        await healthRecordsService.update(type as HealthRecordType, id, transformedData);
        Toast.show({ content: 'Запись обновлена', icon: 'success' });
      } else {
        await healthRecordsService.create(type as HealthRecordType, transformedData);
        Toast.show({ content: 'Запись создана', icon: 'success' });
      }
      
      // Invalidate history query to force refresh
      await queryClient.invalidateQueries({ queryKey: ['history'] });
      
      if (id) {
        setTimeout(() => navigate('/history'), 100);
      } else {
        setTimeout(() => navigate('/'), 100);
      }
    } catch (error) {
      console.error('Error submitting form:', error);
      Toast.show({ content: 'Ошибка при сохранении', icon: 'fail' });
    }
  };

  if (!selectedPetId) {
    return (
      <div style={{ minHeight: '100vh', padding: '16px', backgroundColor: 'var(--app-page-background)' }}>
        <p style={{ color: 'var(--app-text-color)' }}>Выберите животное в меню навигации</p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', backgroundColor: 'var(--app-page-background)' }}>
        <SpinLoading />
      </div>
    );
  }

  const dateTimeFields = config.fields.filter((f: any) => f.name === 'date' || f.name === 'time');
  const otherFields = config.fields.filter((f: any) => f.name !== 'date' && f.name !== 'time');

  return (
    <div style={{ 
      minHeight: '100vh', 
      backgroundColor: 'var(--app-page-background)',
      paddingTop: 'calc(env(safe-area-inset-top) + 88px)',
      paddingBottom: 'calc(env(safe-area-inset-bottom) + 80px)',
      color: 'var(--app-text-color)'
    }}>
      <div style={{ maxWidth: '800px', margin: '0 auto' }}>
        <div style={{ marginBottom: '16px', paddingLeft: 'max(16px, env(safe-area-inset-left))', paddingRight: 'max(16px, env(safe-area-inset-right))' }}>
          <h2 style={{ color: 'var(--app-text-color)', fontSize: '24px', fontWeight: 600, margin: 0 }}>
            {id ? 'Редактирование: ' : ''}{config.title}
          </h2>
        </div>

        <FormProvider {...methods}>
          <Form
            layout="vertical"
            mode="card"
            footer={
              <div style={{ padding: '0 16px 24px' }}>
                <Button
                  type="submit"
                  color="primary"
                  block
                  loading={isSubmitting}
                  disabled={isSubmitting}
                  onClick={handleSubmit(onSubmit)}
                >
                  {isSubmitting ? 'Сохранение...' : 'Сохранить'}
                </Button>
              </div>
            }
          >
            {dateTimeFields.length === 2 && (
              <div style={{ display: 'flex', gap: '8px', width: '100%', alignItems: 'flex-start', padding: '0 16px' }}>
                {dateTimeFields.map((field: any) => (
                  <div 
                    key={field.id} 
                    style={{ 
                      flex: '1 1 0',
                      minWidth: 0, 
                      overflow: 'hidden'
                    }}
                  >
                    <FormField field={field} />
                  </div>
                ))}
              </div>
            )}

            {otherFields.map((field: any) => (
              <FormField 
                key={field.id} 
                field={field} 
                defaultValue={defaultValues[field.name]}
              />
            ))}
          </Form>
        </FormProvider>
      </div>
    </div>
  );
}

