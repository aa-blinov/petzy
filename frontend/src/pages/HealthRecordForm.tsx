import { Fragment, useEffect, useState, useMemo, useCallback } from 'react';
import { showToast } from '../utils/toast';
import { useUnsavedChangesGuard } from '../hooks/useUnsavedChangesGuard';
import { useSessionDraft } from '../hooks/useSessionDraft';
import { deleteWithUndo } from '../utils/deferredDelete';
import { getApiErrorMessage } from '../utils/apiError';
import { useNavigate, useParams, useLocation } from 'react-router-dom';
import { goBack } from '../utils/navigation';
import { useForm, FormProvider } from 'react-hook-form';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button, Form } from 'antd-mobile';
import { usePet } from '../hooks/usePet';
import { useEventTypes } from '../hooks/useEventTypes';
import type { EventType } from '../services/eventTypes.service';
import { isDefaultableField, type FormSettings } from '../utils/formsConfig';
import { petsService, type Pet } from '../services/pets.service';
import { hardBounds, shown } from '../utils/fieldBounds';
import { ChoiceChip, ChoiceChips } from '../components/ChoiceChips';
import { showUndo } from '../utils/undo';
import { formatDate, formatTime } from '../utils/dateUtils';
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

/** The times a record is most often written down for after the fact. */
const WHEN_CHOICES: { label: string; at: (now: Date) => Date }[] = [
  { label: 'Сейчас', at: (now) => now },
  { label: 'Час назад', at: (now) => new Date(now.getTime() - 60 * 60 * 1000) },
  { label: '2 часа назад', at: (now) => new Date(now.getTime() - 2 * 60 * 60 * 1000) },
  { label: 'Вчера в это время', at: (now) => new Date(now.getTime() - 24 * 60 * 60 * 1000) },
];

export function HealthRecordForm() {
  const { type, id } = useParams<{ type: string; id?: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const { selectedPetId, selectedPetName, getSelectedPet } = usePet();
  const queryClient = useQueryClient();
  const { eventTypesByKey, isLoading: eventTypesLoading } = useEventTypes();

  const eventType = type ? eventTypesByKey[type] : undefined;
  const fields = useMemo(() => (eventType ? buildFields(eventType) : []), [eventType]);
  // The field a new record starts at: the first thing it asks to be typed (the portion, the weight), with the keyboard open.
  const firstAskedField = useMemo(() => fields.find((f) => f.required && (f.type === 'number' || f.type === 'text'))?.name, [fields]);
  // The last few values of each number field for this pet: «195, 200» for a portion is one tap.
  const lastRecords = useQuery({
    queryKey: ['recent-values', selectedPetId, type],
    queryFn: () => healthRecordsService.getList(type!, selectedPetId!, 1, 12),
    enabled: !!selectedPetId && !!type && !id,
    staleTime: 60_000,
  });
  const recentValues = useMemo(() => {
    const out: Record<string, string[]> = {};
    for (const field of fields) {
      if (field.type !== 'number') continue;
      const seen: string[] = [];
      for (const record of lastRecords.data?.items ?? []) {
        const raw = record.fields?.[field.name];
        if (raw === undefined || raw === null || raw === '') continue;
        const value = String(raw);
        if (!seen.includes(value)) seen.push(value);
        if (seen.length === 3) break;
      }
      out[field.name] = seen;
    }
    return out;
  }, [fields, lastRecords.data]);

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
          let numberSchema = z.number({
            // An empty field is asked for by name; something that is not a number is told how a number is written.
            error: (issue) => (issue.input === undefined || issue.input === null ? `Укажите: ${field.label.toLowerCase()}` : 'Введите число, например 4,5'),
          });
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
            if (typeof val === 'string') {
              const text = val.replace(/[\s\u00a0\u202f]/g, '').replace(',', '.');
              const number = Number(text);
              return text !== '' && Number.isFinite(number) ? number : val;
            }
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
  // Who wrote the record down: a household of several people looks at this line to know whom to ask.
  const [recordedBy, setRecordedBy] = useState<string | null>(null);

  // The fields of a new record that can hold a default, and which of them came filled from the person's own defaults.
  // The weight itself is what changes each time; everything else about a record can be remembered.
  const defaultableFields = useMemo(
    () => (!isEditing && type ? fields.filter((f) => isDefaultableField(f) && !(type === 'weight' && f.name === 'weight')) : []),
    [isEditing, type, fields],
  );
  // Which fields are remembered for this pet: what the person has switched, else whatever is remembered already.
  const [pinChanged, setPinChanged] = useState<Record<string, boolean>>({});

  const defaultValues = useMemo(() => {
    // The pet's own: its food or drops are about it, and everyone who can add its records starts from the same.
    const settings: FormSettings = getSelectedPet?.form_defaults ?? {};
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
        // A number is shown the way it is typed here, with a comma.
        values[field.name] = field.type === 'number' ? value.replace('.', ',') : value;
      }
    }
    return values;
  }, [isEditing, type, selectedPetId, fields, getSelectedPet]);
  const filledFromDefaults = defaultableFields.filter((f) => !!defaultValues[f.name]);
  const defaultableNames = useMemo(() => new Set(defaultableFields.map((f) => f.name)), [defaultableFields]);
  const isPinned = (name: string) => pinChanged[name] ?? !!defaultValues[name];

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
  useSessionDraft({ dirty: isDirty, getValues: methods.getValues, reset: methods.reset, ready: !!eventType && !isLoading, release });

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
          setRecordedBy(data.username ?? null);
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

      const response: { message: string; id?: string } = id
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

      // What the person asked to remember (the pin under a field) goes to the pet: a pinned field takes the value typed now, an
      // unpinned one that was remembered is forgotten. Nothing is sent when nothing changed.
      let rememberFailed = false;
      if (!id && defaultableFields.length > 0) {
        try {
          const settings = (getSelectedPet?.form_defaults ?? {}) as Record<string, Record<string, string>>;
          const current = { ...(settings[type] ?? {}) };
          const next = { ...current };
          for (const field of defaultableFields) {
            const typed = data[field.name];
            const text = typed === undefined || typed === null ? '' : String(typed).trim();
            if (isPinned(field.name) && text !== '') next[field.name] = text;
            else if (isPinned(field.name) || next[field.name] !== undefined) delete next[field.name];
          }
          if (JSON.stringify(next) !== JSON.stringify(current)) {
            const all = { ...settings };
            if (Object.keys(next).length) all[type] = next;
            else delete all[type];
            const saved = await petsService.saveFormDefaults(selectedPetId, all as FormSettings);
            queryClient.setQueryData<Pet[]>(['pets'], (pets) => pets?.map((p) => (p._id === selectedPetId ? { ...p, form_defaults: saved } : p)));
          }
        } catch {
          rememberFailed = true;
        }
      }

      // A new record can be taken back from the bar that follows, not only by finding it in the feed and deleting it.
      if (!id && response.id) {
        const createdId = response.id;
        showUndo({
          message: response.message,
          onUndo: async () => {
            await healthRecordsService.delete(createdId);
            await queryClient.invalidateQueries({
              predicate: (query) =>
                ['timeline', 'history-timeline', 'stats', 'pet-summary'].includes(query.queryKey[0] as string),
            });
          },
        });
      } else {
        showToast.success(response.message);
      }
      if (rememberFailed) showToast.failure('Запись сохранена, а значения по умолчанию не сохранились');
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
      <div style={{ padding: 'var(--spacing-xl)', textAlign: 'center' }}>
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
            {id ? `${eventType.label}: правка` : `Записать: ${eventType.label}`}
          </h1>
        </div>
        {/* Whose record: with several pets, a form that does not say is a form that may be for the wrong one. */}
        {selectedPetName && (
          <p className="safe-area-padding" style={{ margin: '0 0 var(--spacing-md)', color: 'var(--app-text-secondary)' }}>
            Питомец: <strong style={{ color: 'var(--app-text-primary)' }}>{selectedPetName}</strong>
            {isEditing && recordedBy && <><br />Записал(а): <strong style={{ color: 'var(--app-text-primary)' }}>{recordedBy}</strong></>}
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
              {!isEditing && (
                <div style={{ padding: '0 var(--spacing-md)' }}>
                  <span style={{ fontSize: 'var(--text-xs)', color: 'var(--app-text-secondary)' }} aria-hidden>Когда было</span>
                  {/* Written down afterwards: the common «when» is one tap, not two wheels turned by a finger. */}
                  <ChoiceChips label="Когда">
                    {WHEN_CHOICES.map((choice) => (
                      <ChoiceChip
                        key={choice.label}
                        pressed={false}
                        onClick={() => {
                          const at = choice.at(new Date());
                          methods.setValue('date', formatDate(at), { shouldDirty: true, shouldValidate: true });
                          methods.setValue('time', formatTime(at), { shouldDirty: true, shouldValidate: true });
                        }}
                      >
                        {choice.label}
                      </ChoiceChip>
                    ))}
                  </ChoiceChips>
                </div>
              )}
              <FormField field={{ name: 'date', type: 'date', label: 'Дата', required: true, id: 'event-date' }} defaultValue={defaultValues.date} />
              <FormField field={{ name: 'time', type: 'time', label: 'Время', required: true, id: 'event-time' }} defaultValue={defaultValues.time} />
              {fields.map((field) => (
                <Fragment key={field.id}>
                  <FormField
                    field={field}
                    defaultValue={defaultValues[field.name]}
                    autoFocus={!isEditing && field.name === firstAskedField}
                  />
                  {field.name === filledFromDefaults[filledFromDefaults.length - 1]?.name && (
                    // Under the last field that came filled, so that a value already there is not a surprise: where it came from and where to change it.
                    <p style={{ margin: '0 var(--spacing-md) var(--spacing-sm)', fontSize: 'var(--text-xs)', lineHeight: 1.5, color: 'var(--app-text-secondary)' }}>
                      Подставлено из значений по умолчанию питомца: {filledFromDefaults.map((f) => f.label.toLowerCase()).join(', ')}. Чтобы убрать, снимите «Запоминается» под полем
                    </p>
                  )}
                  {defaultableNames.has(field.name) && (
                    // Remembered for this pet: the next record of this kind starts with what is typed here, and another pet has its own.
                    <div style={{ padding: '0 var(--spacing-md)' }}>
                      <ChoiceChips label="Запоминание">
                        <ChoiceChip pressed={isPinned(field.name)} onClick={() => setPinChanged((prev) => ({ ...prev, [field.name]: !isPinned(field.name) }))}>
                          {isPinned(field.name) ? 'Запоминается для этого питомца' : 'Запомнить для этого питомца'}
                        </ChoiceChip>
                      </ChoiceChips>
                    </div>
                  )}
                  {!isEditing && field.type === 'number' && (recentValues[field.name]?.length ?? 0) > 0 && (
                    // What was given or weighed last time is one tap, not typed from the start again.
                    <div style={{ padding: '0 var(--spacing-md)' }}>
                      <span style={{ fontSize: 'var(--text-xs)', color: 'var(--app-text-secondary)' }} aria-hidden>Как раньше</span>
                      <ChoiceChips label="Как раньше">
                        {recentValues[field.name].map((value) => (
                          <ChoiceChip key={value} pressed={false} onClick={() => methods.setValue(field.name, value, { shouldDirty: true, shouldValidate: true })}>
                            {value.replace('.', ',')}
                          </ChoiceChip>
                        ))}
                      </ChoiceChips>
                    </div>
                  )}
                </Fragment>
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
