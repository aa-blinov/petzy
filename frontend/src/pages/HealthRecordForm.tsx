import { useEffect, useState, useMemo, useCallback } from 'react';
import { showToast } from '../utils/toast';
import { useUnsavedChangesGuard } from '../hooks/useUnsavedChangesGuard';
import { deleteWithUndo } from '../utils/deferredDelete';
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
import { hardBounds, shown } from '../utils/fieldBounds';
import type { FormField as FormFieldType } from '../utils/formsConfig';
import { getCurrentDate, getCurrentTime } from '../utils/dateUtils';
import { healthRecordsService, type HealthRecord } from '../services/healthRecords.service';
import { FormField } from '../components/FormField';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { onInvalidSubmit } from '../utils/formErrors';

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
  const { selectedPetId, selectedPetName } = usePet();
  const queryClient = useQueryClient();
  const { eventTypesByKey, isLoading: eventTypesLoading } = useEventTypes();

  const eventType = type ? eventTypesByKey[type] : undefined;
  const fields = useMemo(() => (eventType ? buildFields(eventType) : []), [eventType]);

  // Create Zod schema dynamically from the type's own fields, plus the
  // date/time/comment every event shares.
  const schema = useMemo(() => {
    const baseFields: Record<string, z.ZodTypeAny> = {
      pet_id: z.string().min(1),
      date: z.string().min(1, 'Укажите дату'),
      time: z.string().min(1, 'Укажите время'),
      comment: z.string().optional(),
    };

    return z.object(
      fields.reduce((acc: Record<string, z.ZodTypeAny>, field) => {
        if (field.type === 'number') {
          // Only enforce a bound the field actually declares — `field.min
          // || 0` used to apply an implicit "can't be negative" to every
          // numeric field, including ones with no declared min at all.
          let numberSchema = z.coerce.number({ error: 'Введите число, например 4,5' });
          const hard = hardBounds(type, field.name);
          const lowest = hard ? Math.max(field.min ?? -Infinity, hard[0]) : field.min;
          const highest = hard ? Math.min(field.max ?? Infinity, hard[1]) : field.max;
          if (lowest !== undefined && Number.isFinite(lowest)) {
            numberSchema = numberSchema.min(lowest, `Не меньше ${shown(lowest)}`);
          }
          if (highest !== undefined && Number.isFinite(highest)) {
            numberSchema = numberSchema.max(highest, `Не больше ${shown(highest)}`);
          }
          const baseSchema = z.preprocess((val) => {
            if (val === '' || val === undefined || val === null) return undefined;
            // A Russian number pad types «4,5»: a comma is a decimal point, and a thin or plain space between thousands is not part of the number.
            if (typeof val === 'string') return val.replace(/[\s\u00a0\u202f]/g, '').replace(',', '.');
            return val;
          }, numberSchema);

          acc[field.name] = field.required ? baseSchema : baseSchema.optional().nullable();
        } else {
          acc[field.name] = field.required
            ? z.string().min(1, 'Заполните это поле')
            : z.string().optional();
        }
        return acc;
      }, baseFields)
    );
  }, [fields, type]);

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
      // Only what the field still offers: a value saved before an option was renamed or dropped would be refused on save.
      const saved = (settings[type as keyof typeof settings] ?? {}) as Record<string, string | undefined>;
      for (const field of fields) {
        const value = saved[field.name];
        if (!value) continue;
        if (field.type === 'select' && field.options && !field.options.some((o) => o.value === value)) continue;
        values[field.name] = value;
      }
    }
    return values;
  }, [isEditing, type, selectedPetId, fields]);

  const methods = useForm({
    // onInvalidSubmit scrolls to and focuses the first error in page order;
    // RHF's own focus picked the first registered ref instead.
    // Validated when a field is left, and after that as it changes: an error
    // shows as soon as it is known, not only after «Сохранить».
    mode: 'onTouched',
    shouldFocusError: false,
    resolver: zodResolver(schema),
    defaultValues
  });

  const {
    handleSubmit,
    formState: { isSubmitting, isDirty },
    reset
  } = methods;
  const { dialog: leaveDialog, release } = useUnsavedChangesGuard(isDirty);

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

      showToast.success(response.message);
      // Leave at once; the toast lives on over the screen we return to
      // (waiting for it to close kept a saved form on screen for two
      // seconds). Not a fixed destination: this form opens from the
      // Dashboard's quick-add (create) and from a tap or edit swipe on
      // either the Dashboard's or History's timeline (edit) — going back
      // lands on whichever of those actually opened it, tab/scroll
      // position and all, instead of assuming History every time an id is
      // present.
      release();
      goBack(navigate, id ? '/history' : '/');
    } catch (error) {
      console.error('Error submitting form:', error);
      const errorMessage = getApiErrorMessage(error, 'Не удалось сохранить');
      showToast.failure(errorMessage);
    }
  };

  if (!selectedPetId) {
    return (
      <div style={{ minHeight: 'var(--app-vh)', padding: '16px', backgroundColor: 'var(--app-page-background)' }}>
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
          <h1 style={{ color: 'var(--app-text-color)', fontSize: 'var(--text-xxl)', fontWeight: 600, margin: 0 }}>
            {id ? 'Редактировать запись' : `Записать: ${eventType.label}`}
          </h1>
        </div>
        {/* Whose record: with several pets, a form that does not say is a form that may be for the wrong one. */}
        {selectedPetName && (
          <p className="safe-area-padding" style={{ margin: '0 0 var(--spacing-md)', color: 'var(--app-text-secondary)' }}>
            Питомец: <strong style={{ color: 'var(--app-text-primary)' }}>{selectedPetName}</strong>
          </p>
        )}

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
              onClick={(e) => { e.preventDefault(); handleSubmit(onSubmit, onInvalidSubmit)(); }}
            />
            <Button
              block
              color="primary"
              size="large"
              onClick={() => handleSubmit(onSubmit, onInvalidSubmit)()}
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
            {id && (
              // Like the swipe on the timeline: no «Удалить эту запись?», the
              // record goes and «Отменить» waits at the bottom.
              <Button
                block
                size="large"
                fill="none"
                color="danger"
                onClick={() => {
                  deleteWithUndo({
                    id,
                    path: `/events/${id}`,
                    message: 'Запись удалена',
                    onDeleted: () =>
                      queryClient.invalidateQueries({
                        predicate: (query) =>
                          ['timeline', 'history-timeline', 'stats', 'pet-summary'].includes(query.queryKey[0] as string),
                      }),
                  });
                  release();
                  goBack(navigate, '/history');
                }}
                style={{ borderRadius: 'var(--radius-md)', fontWeight: 500 }}
              >
                Удалить запись
              </Button>
            )}
          </div>
        </div>
      </div>
      {leaveDialog}
    </div>
  );
}
