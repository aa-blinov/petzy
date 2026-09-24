import { useEffect, useState, useMemo, useCallback } from 'react';
import { showToast } from '../utils/toast';
import { getApiErrorMessage } from '../utils/apiError';
import { useNavigate, useParams, useLocation } from 'react-router-dom';
import { goBack } from '../utils/navigation';
import { useForm, FormProvider } from 'react-hook-form';
import { useQueryClient } from '@tanstack/react-query';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button, Form } from 'antd-mobile';
import { usePet } from '../hooks/usePet';
import { useEventTypes } from '../hooks/useEventTypes';
import type { EventType } from '../services/eventTypes.service';
import { getFormSettings } from '../utils/formsConfig';
import type { FormField as FormFieldType } from '../utils/formsConfig';
import { getCurrentDate, getCurrentTime } from '../utils/dateUtils';
import { healthRecordsService, type HealthRecord } from '../services/healthRecords.service';
import { FormField } from '../components/FormField';
import { LoadingSpinner } from '../components/LoadingSpinner';

/** Builds the field list + title for a registered event type. Date, time
 *  and comment aren't part of `eventType.fields` — every type gets them
 *  the same way, so they're rendered separately (see below) rather than
 *  duplicated into every type's own field list. */
function buildFields(eventType: EventType): FormFieldType[] {
  return eventType.fields.map((f) => ({
    name: f.name,
    type: f.type,
    label: f.label,
    required: f.required,
    options: f.options,
    min: f.min ?? undefined,
    max: f.max ?? undefined,
    step: f.step ?? undefined,
    id: `${eventType.key}-${f.name}`,
  }));
}

export function HealthRecordForm() {
  const { type, id } = useParams<{ type: string; id?: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const { selectedPetId } = usePet();
  const queryClient = useQueryClient();
  const { eventTypesByKey, isLoading: eventTypesLoading } = useEventTypes();

  const eventType = type ? eventTypesByKey[type] : undefined;
  const fields = useMemo(() => (eventType ? buildFields(eventType) : []), [eventType]);

  // Create Zod schema dynamically from the type's own fields, plus the
  // date/time/comment every event shares.
  const schema = useMemo(() => {
    const baseFields: Record<string, z.ZodTypeAny> = {
      pet_id: z.string().min(1),
      date: z.string().min(1, 'Обязательное поле'),
      time: z.string().min(1, 'Обязательное поле'),
      comment: z.string().optional(),
    };

    return z.object(
      fields.reduce((acc: Record<string, z.ZodTypeAny>, field) => {
        if (field.type === 'number') {
          // Only enforce a bound the field actually declares — `field.min
          // || 0` used to apply an implicit "can't be negative" to every
          // numeric field, including ones with no declared min at all.
          let numberSchema = z.coerce.number({ error: 'Введите число' });
          if (field.min !== undefined) {
            numberSchema = numberSchema.min(field.min, `Минимум ${field.min}`);
          }
          if (field.max !== undefined) {
            numberSchema = numberSchema.max(field.max, `Максимум ${field.max}`);
          }
          const baseSchema = z.preprocess((val) => {
            if (val === '' || val === undefined || val === null) return undefined;
            return val;
          }, numberSchema);

          acc[field.name] = field.required ? baseSchema : baseSchema.optional().nullable();
        } else {
          acc[field.name] = field.required
            ? z.string().min(1, 'Обязательное поле')
            : z.string().optional();
        }
        return acc;
      }, baseFields)
    );
  }, [fields]);

  const isEditing = !!id;
  const [isLoading, setIsLoading] = useState(isEditing);

  const defaultValues = useMemo(() => {
    const settings = getFormSettings();
    const values: Record<string, string | undefined> = {
      date: isEditing ? '' : getCurrentDate(),
      time: isEditing ? '' : getCurrentTime(),
      pet_id: selectedPetId || '',
      comment: '',
    };

    for (const field of fields) {
      values[field.name] = field.type === 'number' ? undefined : '';
    }

    if (!isEditing && type && type in settings) {
      Object.assign(values, settings[type as keyof typeof settings]);
    }
    return values;
  }, [isEditing, type, selectedPetId, fields]);

  const methods = useForm({
    resolver: zodResolver(schema),
    defaultValues
  });

  const {
    handleSubmit,
    formState: { isSubmitting },
    reset
  } = methods;

  // Maps an API record (date_time + nested fields) onto the form's flat
  // field names — the mirror image of onSubmit's payload building below.
  const normalizeData = useCallback((data: HealthRecord) => {
    const formData: Record<string, unknown> = {
      pet_id: data.pet_id || selectedPetId || '',
      comment: data.comment ?? '',
    };

    if (data.date_time) {
      const parts = String(data.date_time).split(' ');
      formData.date = parts[0] || '';
      formData.time = parts[1] ? String(parts[1]).substring(0, 5) : '';
    } else {
      formData.date = data.date ? String(data.date) : '';
      formData.time = data.time ? String(data.time) : '';
    }

    const rawFields = data.fields ?? {};
    for (const field of fields) {
      const raw = rawFields[field.name];
      if (field.type === 'select' && field.options) {
        const norm = raw !== undefined && raw !== null ? String(raw).trim() : '';
        const match = field.options.find((opt) => String(opt.value) === norm);
        formData[field.name] = match ? String(match.value) : norm;
      } else if (field.type === 'number') {
        formData[field.name] = raw !== undefined && raw !== null && raw !== '' ? raw : '';
      } else {
        formData[field.name] = raw !== undefined && raw !== null ? String(raw) : '';
      }
    }

    return formData;
  }, [fields, selectedPetId]);

  useEffect(() => {
    if (!selectedPetId) {
      navigate('/');
    }
  }, [selectedPetId, navigate]);

  useEffect(() => {
    if (!eventType) return;

    if (isEditing) {
      if (!type) return;
      const loadData = async () => {
        try {
          let data = location.state?.recordData as HealthRecord | undefined;
          if (!data) {
            setIsLoading(true);
            data = await healthRecordsService.get(id!);
          }
          reset(normalizeData(data));
        } catch (err) {
          console.error('Error loading record:', err);
          showToast.failure('Не удалось загрузить запись');
          navigate('/history');
        } finally {
          setIsLoading(false);
        }
      };
      loadData();
    } else {
      reset(defaultValues);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isEditing, type, id, location.state, normalizeData, reset, navigate, !!eventType]);

  const onSubmit = async (data: Record<string, unknown>) => {
    if (!selectedPetId || !type || !eventType) return;

    try {
      const fieldsPayload: Record<string, unknown> = {};
      for (const field of fields) {
        fieldsPayload[field.name] = data[field.name];
      }
      const payload = {
        pet_id: selectedPetId,
        // Zod's resolver already enforced these as non-empty strings
        // before react-hook-form ever calls this handler.
        date: data.date as string,
        time: data.time as string,
        comment: (data.comment as string) || '',
        fields: fieldsPayload,
      };

      const response = id
        ? await healthRecordsService.update(id, payload)
        : await healthRecordsService.create(type, payload);

      // Dashboard, History and PetSummaryCard each key their queries
      // differently ('timeline', 'history-timeline', 'stats', 'pet-summary')
      // — none of them start with 'history', so a plain
      // invalidateQueries(['history']) silently matched nothing and every
      // view kept showing pre-submit data until its own staleTime lapsed.
      await queryClient.invalidateQueries({
        predicate: (query) =>
          ['timeline', 'history-timeline', 'stats', 'pet-summary'].includes(query.queryKey[0] as string),
      });

      showToast.success(response.message, {
        // Not a fixed destination: this form opens from the Dashboard's
        // quick-add (create) and from an edit swipe on either the
        // Dashboard's or History's timeline (edit) — going back lands on
        // whichever of those actually opened it, tab/scroll position and
        // all, instead of assuming History every time an id is present.
        afterClose: () => goBack(navigate, id ? '/history' : '/'),
      });
    } catch (error) {
      console.error('Error submitting form:', error);
      const errorMessage = getApiErrorMessage(error, 'Не удалось сохранить');
      showToast.failure(errorMessage);
    }
  };

  if (!selectedPetId) {
    return (
      <div style={{ minHeight: '100vh', padding: '16px', backgroundColor: 'var(--app-page-background)' }}>
        <p style={{ color: 'var(--app-text-color)' }}>Выберите питомца в меню навигации</p>
      </div>
    );
  }

  if (eventTypesLoading || isLoading) {
    return <LoadingSpinner />;
  }

  if (!type || !eventType) {
    return (
      <div style={{ padding: '20px', textAlign: 'center' }}>
        <p>Неизвестный тип записи</p>
        <Button onClick={() => navigate('/')}>На главную</Button>
      </div>
    );
  }

  return (
    <div className="page-container">
      <div className="max-width-container">
        <div className="safe-area-padding" style={{
          marginBottom: 'var(--spacing-lg)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          minHeight: '40px'
        }}>
          <h2 style={{ color: 'var(--app-text-color)', fontSize: 'var(--text-xxl)', fontWeight: 600, margin: 0 }}>
            {id ? 'Редактировать запись' : `Записать: ${eventType.label}`}
          </h2>
        </div>

        <div>
          <FormProvider {...methods}>
            <Form
              layout="horizontal"
              mode="card"
              style={{
                '--prefix-width': '7em'
              } as React.CSSProperties}
            >
              <FormField field={{ name: 'date', type: 'date', label: 'Дата', required: true, id: 'event-date' }} defaultValue={defaultValues.date} />
              <FormField field={{ name: 'time', type: 'time', label: 'Время', required: true, id: 'event-time' }} defaultValue={defaultValues.time} />
              {fields.map((field) => (
                <FormField
                  key={field.id}
                  field={field}
                  defaultValue={defaultValues[field.name]}
                />
              ))}
              <FormField
                field={{ name: 'comment', type: 'textarea', label: 'Комментарий (необязательно)', rows: 2, id: 'event-comment' }}
                defaultValue={defaultValues.comment}
              />
            </Form>
          </FormProvider>

          <div className="safe-area-padding" style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--spacing-md)',
            marginTop: 'var(--spacing-xl)',
            paddingBottom: 'var(--spacing-xl)',
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
              style={{ borderRadius: 'var(--radius-md)', fontWeight: 600 }}
            >
              {id ? 'Сохранить' : 'Создать'}
            </Button>
            <Button
              block
              size="large"
              onClick={() => goBack(navigate, id ? '/history' : '/')}
              style={{ borderRadius: 'var(--radius-md)', fontWeight: 500 }}
            >
              Отмена
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
