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
  const config = useMemo(() =>
    type && type in formConfigs ? formConfigs[type as HealthRecordType] : null
    , [type]);

  // Create Zod schema dynamically
  const schema = useMemo(() => {
    // Используем базовое поле, чтобы объект не был пустым (Record<string, never>)
    const baseFields: Record<string, any> = {
      pet_id: z.string().min(1)
    };

    if (!config) return z.object(baseFields);

    return z.object(
      config.fields.reduce((acc: Record<string, any>, field: any) => {
        if (field.type === 'number') {
          // Для обязательных чисел: не разрешаем пустую строку
          const baseSchema = z.preprocess((val) => {
            if (val === '' || val === undefined || val === null) return undefined;
            return val;
          }, z.coerce.number({
            error: 'Введите число'
          }).min(field.min || 0, `Минимум ${field.min || 0}`));

          acc[field.name] = field.required
            ? baseSchema
            : baseSchema.optional().nullable();
        } else {
          acc[field.name] = field.required
            ? z.string().min(1, 'Обязательное поле')
            : z.string().optional();
        }
        return acc;
      }, baseFields)
    );
  }, [config]);

  // Если мы редактируем, нам не нужны дефолтные значения "сейчас", 
  // иначе может быть скачок данных.
  const isEditing = !!id;
  const [isLoading, setIsLoading] = useState(isEditing);

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

  if (!type || !config) {
    return (
      <div style={{ padding: '20px', textAlign: 'center' }}>
        <p>Неизвестный тип записи или конфигурация отсутствует</p>
        <Button onClick={() => navigate('/')}>На главную</Button>
      </div>
    );
  }

  // Единая функция нормализации данных
  const normalizeData = useCallback((data: any) => {
    if (!config) return {};

    console.log('Normalize input data:', data);

    const formData: Record<string, any> = {
      pet_id: data.pet_id || data.petId || selectedPetId || '',
    };

    // Date/Time handling
    if (data.date_time) {
      const parts = String(data.date_time).split(' ');
      formData.date = parts[0] || '';
      formData.time = parts[1] ? String(parts[1]).substring(0, 5) : '';
    } else if (data.date || data.time) {
      formData.date = data.date ? String(data.date) : '';
      formData.time = data.time ? String(data.time) : '';
    } else {
      formData.date = '';
      formData.time = '';
    }

    // Process only fields defined in form config
    config.fields.forEach((field: any) => {
      if (field.name === 'date' || field.name === 'time') return;

      // Robust field searching: exact, then case-insensitive, then ignoring underscores
      let raw = data[field.name];
      if (raw === undefined) {
        const keys = Object.keys(data);
        const lowerName = field.name.toLowerCase();
        const simpleName = lowerName.replace(/_/g, '');

        const foundKey = keys.find(k => {
          const lk = k.toLowerCase();
          return lk === lowerName || lk.replace(/_/g, '') === simpleName;
        });

        if (foundKey) {
          raw = data[foundKey];
        }
      }

      // Unwrap objects
      if (raw && typeof raw === 'object' && !Array.isArray(raw)) {
        if (raw.value !== undefined && raw.value !== null) raw = raw.value;
        else if (raw.id !== undefined && raw.id !== null) raw = raw.id;
      }

      let finalValue: any = raw ?? '';

      if (field.type === 'select' && field.options) {
        const norm = String(raw !== undefined && raw !== null ? raw : '').trim().toLowerCase();
        const optsLower = field.options.map((o: any) => String(o.value).toLowerCase());
        const isBoolSelect = optsLower.includes('true') && optsLower.includes('false');

        if (isBoolSelect) {
          const isTrue = [true, 'true', '1', 'yes', 'да'].includes(norm) || raw === true;
          const isFalse = [false, 'false', '0', 'no', 'нет'].includes(norm) || raw === false;
          finalValue = isTrue ? 'true' : (isFalse ? 'false' : '');
        } else if (norm !== '') {
          const matchingOption = field.options.find((opt: any) => {
            const optVal = String(opt.value).trim().toLowerCase();
            const optText = String(opt.text || '').trim().toLowerCase();
            return optVal === norm || optText === norm;
          });
          if (matchingOption) finalValue = String(matchingOption.value);
          else finalValue = String(raw);
        } else {
          finalValue = '';
        }
      } else if (field.type === 'number') {
        if (raw !== undefined && raw !== null && raw !== '') {
          const numValue = typeof raw === 'number' ? raw : parseFloat(String(raw).replace(',', '.'));
          finalValue = !isNaN(numValue) && isFinite(numValue) ? numValue : '';
        } else {
          finalValue = '';
        }
      } else {
        finalValue = raw !== undefined && raw !== null ? String(raw) : '';
      }

      formData[field.name] = finalValue;
    });

    console.log('Normalize output data:', formData);
    return formData;
  }, [config, selectedPetId]);

  // Initial check for selected pet
  useEffect(() => {
    if (!selectedPetId) {
      navigate('/');
    }
  }, [selectedPetId, navigate]);

  // Эффект загрузки данных при редактировании или сброса для новой записи
  useEffect(() => {
    if (isEditing) {
      if (!type) return;
      const loadData = async () => {
        try {
          let data = location.state?.recordData;
          if (!data) {
            setIsLoading(true);
            data = await healthRecordsService.get(type as HealthRecordType, id!);
          }
          const formData = normalizeData(data);
          const safeFormData: Record<string, any> = {};
          Object.keys(formData).forEach(key => {
            safeFormData[key] = formData[key] ?? '';
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
    } else {
      // Для новой записи сбрасываем форму в дефолтные значения
      reset(defaultValues);
    }
  }, [isEditing, type, id, location.state, normalizeData, reset, navigate, defaultValues]);

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
              layout="horizontal"
              mode="card"
            >
              {config.fields.map((field) => (
                <FormField
                  key={field.id}
                  field={field}
                  defaultValue={defaultValues[field.name]}
                />
              ))}
            </Form>
          </FormProvider>

          <div style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
            marginTop: '24px',
            paddingBottom: '24px'
          }}>
            <button
              style={{ display: 'none' }}
              type="submit"
              onClick={(e) => { e.preventDefault(); handleSubmit(onSubmit)(); }}
            />
            <Button
              block
              color="primary"
              size="large"
              onClick={() => handleSubmit(onSubmit)()}
              loading={isSubmitting}
              style={{ borderRadius: '12px', fontWeight: 600 }}
            >
              {id ? 'Сохранить' : 'Создать'}
            </Button>
            <Button
              block
              size="large"
              onClick={() => {
                if (id) {
                  const activeTab = searchParams.get('tab');
                  navigate(activeTab ? `/history?tab=${activeTab}` : '/history');
                } else {
                  navigate('/');
                }
              }}
              style={{ borderRadius: '12px', fontWeight: 500 }}
            >
              Отмена
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
