import { useEffect, useState, useMemo, useCallback } from 'react';
import { useNavigate, useParams, useLocation, useSearchParams } from 'react-router-dom';
import { useForm, FormProvider } from 'react-hook-form';
import { useQueryClient } from '@tanstack/react-query';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button, Form, Toast } from 'antd-mobile';
import { usePet } from '../hooks/usePet';
import { formConfigs, getFormSettings } from '../utils/formsConfig';
import type { HealthRecordType } from '../utils/constants';
import { getCurrentDate, getCurrentTime } from '../utils/dateUtils';
import { healthRecordsService } from '../services/healthRecords.service';
import { FormField } from '../components/FormField';
import { LoadingSpinner } from '../components/LoadingSpinner';

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

  // При редактировании начальные значения помогут react-hook-form инициализировать поля,
  // а затем они будут обновлены вызовом reset() в useEffect когда данные будут загружены.
  const defaultValues = useMemo(() => {
    const settings = getFormSettings();
    const values: Record<string, any> = {
      date: isEditing ? '' : getCurrentDate(),
      time: isEditing ? '' : getCurrentTime(),
      pet_id: selectedPetId || ''
    };

    // Добавляем поля из конфига, чтобы RHF знал о них
    if (config) {
      config.fields.forEach(field => {
        if (field.name === 'date' || field.name === 'time') return;
        values[field.name] = field.type === 'number' ? undefined : '';
      });
    }

    if (!isEditing && type && type in settings && settings[type as keyof typeof settings]) {
      Object.assign(values, settings[type as keyof typeof settings]);
    }
    return values;
  }, [isEditing, type, selectedPetId, config]);

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
    // First prefer combined date_time, but also support legacy separate date/time fields
    if (data.date_time) {
      const [datePart, timePart] = String(data.date_time).split(' ');
      formData.date = datePart || '';
      formData.time = timePart ? String(timePart).substring(0, 5) : '';
    } else if (data.date || data.time) {
      // Support records that store date and time separately
      formData.date = data.date ? String(data.date) : '';
      formData.time = data.time ? String(data.time) : '';
    } else {
      // If there's no date in DB, explicitly clear values so defaultValues won't remain
      formData.date = '';
      formData.time = '';
    }

    // Process only fields defined in form config
    config.fields.forEach((field: any) => {
      if (field.name === 'date' || field.name === 'time') return;

      // Try exact match first, then case-insensitive match
      let raw = data[field.name];
      if (raw === undefined) {
        const lowerName = field.name.toLowerCase();
        const foundKey = Object.keys(data).find(k => k.toLowerCase() === lowerName);
        if (foundKey) {
          raw = data[foundKey];
        }
      }

      // Unwrap objects like { value: 'x' } or { id: 'x' }
      if (raw && typeof raw === 'object' && !Array.isArray(raw)) {
        if (raw.value !== undefined && raw.value !== null) raw = raw.value;
        else if (raw.id !== undefined && raw.id !== null) raw = raw.id;
      }

      // Default empty
      let finalValue: any = raw ?? '';

      if (field.type === 'select' && field.options) {
        // Normalize string for comparisons
        const norm = raw !== undefined && raw !== null ? String(raw).trim() : '';

        // Generic boolean-like select handling if options are 'true'/'false'
        const optsLower = field.options.map((o: any) => String(o.value).toLowerCase());
        const isBoolSelect = optsLower.includes('true') && optsLower.includes('false');
        if (isBoolSelect) {
          const v = String(norm).toLowerCase();
          if (['true', '1', 'yes', 'да'].includes(v)) finalValue = 'true';
          else if (['false', '0', 'no', 'нет'].includes(v)) finalValue = 'false';
          else finalValue = '';
        } else if (norm !== '') {
          // Find option by value or text (case-insensitive)
          const matchingOption = field.options.find((opt: any) => {
            const optVal = String(opt.value).trim().toLowerCase();
            const optText = String(opt.text || '').trim().toLowerCase();
            const rawNorm = String(norm).trim().toLowerCase();
            return optVal === rawNorm || optText === rawNorm;
          });
          if (matchingOption) finalValue = String(matchingOption.value);
          else {
            finalValue = String(raw);
          }
        } else {
          finalValue = '';
        }
      } else if (field.type === 'number') {
        if (raw !== undefined && raw !== null && raw !== '') {
          if (typeof raw === 'number') {
            finalValue = raw;
          } else {
            const rawStr = String(raw).replace(',', '.');
            const match = rawStr.match(/-?\d+(?:\.\d+)?/);
            const numValue = match ? parseFloat(match[0]) : NaN;
            if (!isNaN(numValue) && isFinite(numValue)) finalValue = numValue;
            else finalValue = '';
          }
        } else {
          finalValue = '';
        }
      } else {
        // For text and textarea, ensure it's a string
        finalValue = raw !== undefined && raw !== null ? String(raw) : '';
      }

      // Всегда добавляем ключ в formData, даже если значение пустое
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
        }

        const formData = normalizeData(data);

        console.log('Resetting form with:', formData);

        // Ensure all values are properly typed for react-hook-form
        const safeFormData: Record<string, any> = {};
        Object.keys(formData).forEach(key => {
          const value = formData[key];
          if (value === undefined || value === null) {
            safeFormData[key] = '';
          } else {
            safeFormData[key] = value;
          }
        });

        reset(safeFormData);
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
        Toast.show({ content: config.successMessage(true), icon: 'success', duration: 1500 });
      } else {
        await healthRecordsService.create(type as HealthRecordType, transformedData);
        Toast.show({ content: config.successMessage(false), icon: 'success', duration: 1500 });
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
    } catch (error: any) {
      console.error('Error submitting form:', error);
      const errorMessage = error.response?.data?.error || 'Ошибка при сохранении';
      Toast.show({ content: errorMessage, icon: 'fail' });
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
    return <LoadingSpinner />;
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
              style={{
                '--background-color': 'var(--app-card-background)',
                '--border-top': 'none',
                '--border-bottom': 'none',
                '--border-inner': '1px solid var(--app-border-color)',
                borderRadius: '12px',
                overflow: 'hidden',
                boxShadow: '0 2px 8px rgba(0, 0, 0, 0.05)',
              } as any}
            >
              {config.fields.map((field) => (
                <FormField key={field.id} field={field} />
              ))}
            </Form>
          </FormProvider>

          <div style={{ display: 'flex', gap: '8px', marginTop: '16px' }}>
            <Button
              onClick={() => {
                if (id) {
                  const activeTab = searchParams.get('tab');
                  navigate(activeTab ? `/history?tab=${activeTab}` : '/history');
                } else {
                  navigate('/');
                }
              }}
              style={{ flex: 1 }}
            >
              Отмена
            </Button>
            <Button
              onClick={() => handleSubmit(onSubmit)()}
              color="primary"
              loading={isSubmitting}
              style={{ flex: 1 }}
            >
              {id ? 'Сохранить' : 'Создать'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
