import { useEffect, useState, useMemo, useCallback } from 'react';
import { useNavigate, useParams, useLocation, useSearchParams } from 'react-router-dom';
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
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const { selectedPetId } = usePet();
  const queryClient = useQueryClient();
  const config = type && type in formConfigs ? formConfigs[type as HealthRecordType] : null;
  
  // Если мы редактируем, нам не нужны дефолтные значения "сейчас", 
  // иначе может быть скачок данных.
  const isEditing = !!id;
  const [isLoading, setIsLoading] = useState(isEditing);

  if (!type || !config) {
    return <div>Неизвестный тип записи</div>;
  }

  // Create Zod schema dynamically
  const schema = useMemo(() => {
    return z.object(
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
  }, [config]);

  // Дефолтные значения только для НОВОЙ записи
  const defaultValues = useMemo(() => {
    if (isEditing) return undefined; // При редактировании данные придут из reset()

    const settings = getFormSettings();
    const values: Record<string, any> = {
      date: getCurrentDate(),
      time: getCurrentTime(),
      pet_id: selectedPetId || ''
    };

    if (type && type in settings && settings[type as keyof typeof settings]) {
      Object.assign(values, settings[type as keyof typeof settings]);
    }
    return values;
  }, [isEditing, type, selectedPetId]);

  const methods = useForm({
    resolver: zodResolver(schema),
    defaultValues
  });

  const {
    handleSubmit,
    formState: { isSubmitting },
    reset
  } = methods;

  // Единая функция нормализации данных
  const normalizeData = useCallback((data: any) => {
    if (!config) return {};

    const formData: Record<string, any> = {
      pet_id: data.pet_id || selectedPetId || '',
    };

    // Date/Time handling
    if (data.date_time) {
      const [datePart, timePart] = data.date_time.split(' ');
      formData.date = datePart || '';
      formData.time = timePart ? timePart.substring(0, 5) : '';
    } else {
      // Важно: если даты нет в БД, явно сбрасываем, чтобы не осталось defaultValues
      formData.date = '';
      formData.time = '';
    }

    config.fields.forEach((field: any) => {
      if (field.name === 'date' || field.name === 'time') return;

      const value = data[field.name];

      // Важно: По умолчанию ставим пустую строку или null, если значения нет,
      // чтобы перезаписать возможные старые значения формы
      let finalValue: any = value ?? '';

      if (field.type === 'select' && field.options) {
        if (field.name === 'inhalation') {
          if (String(value) === 'true' || value === true || value === 'Да') {
            finalValue = 'true';
          } else if (String(value) === 'false' || value === false || value === 'Нет') {
            finalValue = 'false';
          } else {
            finalValue = '';
          }
        } else if (value) {
          const matchingOption = field.options.find((opt: any) => 
            opt.text === value || opt.value === value
          );
          if (matchingOption) {
            finalValue = matchingOption.value;
          } else {
            console.warn(`No matching option found for field ${field.name} with value:`, value);
            finalValue = value;
          }
        } else {
          finalValue = '';
        }
      } else if (field.type === 'number') {
        if (value !== undefined && value !== null && value !== '') {
          const numValue = typeof value === 'number' ? value : parseFloat(String(value));
          if (!isNaN(numValue) && isFinite(numValue)) {
            finalValue = numValue;
          } else {
            console.warn(`Invalid number value for field ${field.name}:`, value);
            finalValue = '';
          }
        } else {
          finalValue = '';
        }
      } else {
        // Text and textarea - allow empty strings (they should be reset)
        finalValue = value ?? '';
      }

      // Всегда добавляем ключ в formData, даже если значение пустое
      // Это важно для правильного сброса defaultValues
      formData[field.name] = finalValue;
    });

    return formData;
  }, [config, selectedPetId]);

  // Initial check for selected pet
  useEffect(() => {
    if (!selectedPetId) {
      navigate('/');
    }
  }, [selectedPetId, navigate]);

  // Эффект загрузки данных при редактировании
  useEffect(() => {
    if (!isEditing || !type) return;

    const loadData = async () => {
      try {
        let data = location.state?.recordData;

        if (!data) {
          setIsLoading(true);
          data = await healthRecordsService.get(type as HealthRecordType, id!);
        } else {
          setIsLoading(false);
        }

        const formData = normalizeData(data);
        
        console.log('Resetting form with:', formData);
        reset(formData); // Вызываем синхронно, без setTimeout
      } catch (err) {
        console.error('Error loading record:', err);
        Toast.show({ content: 'Ошибка загрузки записи', icon: 'fail' });
        navigate('/history');
      } finally {
        setIsLoading(false);
      }
    };

    loadData();
  }, [isEditing, type, id, location.state, normalizeData, reset, navigate]);

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
        Toast.show({ content: 'Запись обновлена', icon: 'success', duration: 1500 });
      } else {
        await healthRecordsService.create(type as HealthRecordType, transformedData);
        Toast.show({ content: 'Запись создана', icon: 'success', duration: 1500 });
      }
      
      await queryClient.invalidateQueries({ queryKey: ['history'] });
      
      // Навигация
      if (id) {
        // При редактировании возвращаемся на историю с сохранением активной вкладки из URL
        const activeTab = searchParams.get('tab');
        navigate(activeTab ? `/history?tab=${activeTab}` : '/history');
      } else {
        // При создании новой записи возвращаемся на главную
        navigate('/');
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

  return (
    <div
      style={{
        minHeight: '100vh',
        paddingTop: 'calc(env(safe-area-inset-top) + 88px)',
        paddingBottom: 'calc(env(safe-area-inset-bottom) + 80px)',
        backgroundColor: 'var(--app-page-background)',
        color: 'var(--app-text-color)'
      }}
    >
      <div style={{ maxWidth: '800px', margin: '0 auto' }}>
        <div style={{ 
          marginBottom: '16px', 
          paddingLeft: 'max(16px, env(safe-area-inset-left))', 
          paddingRight: 'max(16px, env(safe-area-inset-right))' 
        }}>
          <h2 style={{ color: 'var(--app-text-color)', fontSize: '24px', fontWeight: 600, margin: 0 }}>
            {id ? 'Редактировать запись' : config.title}
          </h2>
        </div>

        <div style={{ 
          paddingLeft: 'max(16px, env(safe-area-inset-left))',
          paddingRight: 'max(16px, env(safe-area-inset-right))'
        }}>
          <FormProvider {...methods}>
            <Form
              onFinish={handleSubmit(onSubmit)}
              footer={
                <div style={{ display: 'flex', gap: '8px', marginTop: '16px' }}>
                  <Button
                    onClick={() => {
                      if (id) {
                        // При редактировании возвращаемся на историю с сохранением активной вкладки из URL
                        const activeTab = searchParams.get('tab');
                        navigate(activeTab ? `/history?tab=${activeTab}` : '/history');
                      } else {
                        // При создании новой записи возвращаемся на главную
                        navigate('/');
                      }
                    }}
                    style={{ flex: 1 }}
                  >
                    Отмена
                  </Button>
                  <Button
                    type="submit"
                    color="primary"
                    loading={isSubmitting}
                    style={{ flex: 1 }}
                  >
                    {id ? 'Сохранить' : 'Создать'}
                  </Button>
                </div>
              }
            >
              {config.fields.map((field) => (
                <FormField key={field.id} field={field} />
              ))}
            </Form>
          </FormProvider>
        </div>
      </div>
    </div>
  );
}
