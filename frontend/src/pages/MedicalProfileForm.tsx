import { useEffect, useRef } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useFieldArray, useForm, Controller, useWatch } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button, Form, Input, Switch } from 'antd-mobile';
import { DeleteOutline } from 'antd-mobile-icons';
import { medicalCardService } from '../services/medicalCard.service';
import { LoadError } from '../components/LoadError';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { SpinnerButton } from '../components/SpinnerButton';
import { FieldError } from '../components/FieldError';
import { fieldNote } from '../components/FieldNote';
import { useUnsavedChangesGuard } from '../hooks/useUnsavedChangesGuard';
import { onInvalidSubmit } from '../utils/formErrors';
import { goBack } from '../utils/navigation';
import { showToast } from '../utils/toast';
import { confirmWithProgress } from '../utils/medicalReadiness';
import { getApiErrorMessage } from '../utils/apiError';

const currentYear = new Date().getFullYear();

const profileSchema = z.object({
  chip_number: z.string().max(30).optional(),
  blood_type: z.string().max(20).optional(),
  allergies_none_known: z.boolean(),
  allergies: z.array(
    z.object({
      substance: z.string().trim().min(1, 'Укажите, на что аллергия').max(100),
      reaction: z.string().max(200).optional(),
    }),
  ),
  conditions: z.array(
    z.object({
      name: z.string().trim().min(1, 'Укажите состояние или диагноз').max(100),
      since_year: z
        .string()
        .regex(/^(\d{4})?$/, 'Четыре цифры, например 2023')
        .refine((v) => v === '' || (Number(v) >= 1950 && Number(v) <= currentYear), `С 1950 по ${currentYear}`)
        .optional(),
      note: z.string().max(300).optional(),
    }),
  ),
  clinic: z.object({
    name: z.string().max(100).optional(),
    vet: z.string().max(100).optional(),
    phone: z.string().max(30).optional(),
  }),
});

type ProfileForm = z.infer<typeof profileSchema>;

const EMPTY: ProfileForm = {
  chip_number: '',
  blood_type: '',
  allergies_none_known: false,
  allergies: [],
  conditions: [],
  clinic: { name: '', vet: '', phone: '' },
};

const textProps = { style: { '--text-align': 'left' } as React.CSSProperties };

/** What a vet asks first: allergies, chronic conditions, chip, blood type and the clinic.
    Kept on the pet and open to everyone who has access to it, like the weight. */
export function MedicalProfileForm() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const cardPath = `/pets/${id}/medical-card`;

  const query = useQuery({
    queryKey: ['medical-card', id],
    queryFn: () => medicalCardService.get(id!),
    enabled: !!id,
    staleTime: 0,
    refetchOnMount: 'always',
  });

  const { control, handleSubmit, reset, setValue, getValues, formState: { isDirty, isSubmitting } } = useForm<ProfileForm>({
    mode: 'onTouched',
    shouldFocusError: false,
    resolver: zodResolver(profileSchema),
    defaultValues: EMPTY,
  });
  const allergies = useFieldArray({ control, name: 'allergies' });
  const conditions = useFieldArray({ control, name: 'conditions' });
  const noneKnown = useWatch({ control, name: 'allergies_none_known' });
  const { dialog: leaveDialog, release } = useUnsavedChangesGuard(isDirty);

  // The saved profile goes into the form once, when it arrives.
  const loaded = useRef(false);
  const section = useSearchParams()[0].get('section');
  useEffect(() => {
    const profile = query.data?.profile;
    if (!profile || loaded.current) return;
    loaded.current = true;
    // Opened from «Указать клинику»: the form starts at the clinic, with the cursor in its first field.
    if (section === 'clinic') {
      window.setTimeout(() => {
        const anchor = document.getElementById('medprofile-clinic');
        anchor?.scrollIntoView({ block: 'start' });
        document.querySelector<HTMLInputElement>('input[placeholder="Где наблюдается"]')?.focus({ preventScroll: true });
      }, 80);
    }
    reset({
      chip_number: profile.chip_number ?? '',
      blood_type: profile.blood_type ?? '',
      allergies_none_known: profile.allergies_none_known,
      allergies: profile.allergies.map((a) => ({ substance: a.substance, reaction: a.reaction ?? '' })),
      conditions: profile.conditions.map((c) => ({ name: c.name, since_year: c.since_year ? String(c.since_year) : '', note: c.note ?? '' })),
      clinic: { name: profile.clinic.name ?? '', vet: profile.clinic.vet ?? '', phone: profile.clinic.phone ?? '' },
    });
  }, [query.data, reset, section]);

  const save = useMutation({
    mutationFn: (data: ProfileForm) =>
      medicalCardService.saveProfile(id!, {
        chip_number: data.chip_number?.trim() || null,
        blood_type: data.blood_type?.trim() || null,
        allergies_none_known: data.allergies_none_known,
        // A row left completely empty is not an entry.
        allergies: data.allergies_none_known
          ? []
          : data.allergies.filter((a) => a.substance.trim() || a.reaction?.trim()).map((a) => ({ substance: a.substance.trim(), reaction: a.reaction?.trim() || null })),
        conditions: data.conditions.map((c) => ({ name: c.name.trim(), since_year: c.since_year ? Number(c.since_year) : null, note: c.note?.trim() || null })),
        clinic: { name: data.clinic.name?.trim() || null, vet: data.clinic.vet?.trim() || null, phone: data.clinic.phone?.trim() || null },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['medical-card', id] });
      queryClient.invalidateQueries({ queryKey: ['pets'] });
      void confirmWithProgress(queryClient, id!, 'Данные для врача сохранены');
      release();
      goBack(navigate, cardPath);
    },
    onError: (err: unknown) => {
      showToast.failure(getApiErrorMessage(err, 'Не удалось сохранить'));
    },
  });

  // A row added and left completely empty is not an entry: it goes before the
  // form is checked, instead of being an error about a field nobody filled.
  const pruneEmptyRows = () => {
    const values = getValues();
    const empty = <T,>(rows: T[], filled: (row: T) => boolean) => rows.map((row, i) => (filled(row) ? -1 : i)).filter((i) => i >= 0);
    const emptyAllergies = empty(values.allergies, (a) => !!(a.substance?.trim() || a.reaction?.trim()));
    if (emptyAllergies.length) allergies.remove(emptyAllergies);
    const emptyConditions = empty(values.conditions, (c) => !!(c.name?.trim() || c.since_year?.trim() || c.note?.trim()));
    if (emptyConditions.length) conditions.remove(emptyConditions);
  };

  if (query.isError) {
    return (
      <div className="page-container">
        <div className="max-width-container safe-area-padding">
          <LoadError what="данные для врача" onRetry={() => query.refetch()} />
        </div>
      </div>
    );
  }
  if (!query.data) return <LoadingSpinner />;

  const onSubmit = (data: ProfileForm) => save.mutate(data);

  return (
    <div className="page-container">
      <div className="max-width-container">
        <div className="safe-area-padding" style={{ marginBottom: 'var(--spacing-lg)' }}>
          <h1 style={{ color: 'var(--app-text-color)', fontSize: 'var(--text-xxl)', fontWeight: 600, margin: 0 }}>Данные для врача</h1>
          <p style={{ margin: '4px 0 0', fontSize: 'var(--text-sm)', color: 'var(--app-text-secondary)' }}>
            Это видят все, у кого есть доступ к питомцу {query.data.pet.name}, и врач в PDF
          </p>
        </div>

        <Form layout="vertical" mode="card">
          <Form.Header>Аллергии</Form.Header>
          <Controller
            name="allergies_none_known"
            control={control}
            render={({ field }) => (
              <Form.Item
                layout="horizontal"
                label="Аллергий нет"
                description="Врач увидит «не выявлено», а не «не указаны»"
                extra={
                  <Switch
                    checked={field.value}
                    onChange={(on) => {
                      field.onChange(on);
                      if (on) setValue('allergies', [], { shouldDirty: true });
                    }}
                  />
                }
              />
            )}
          />
          {!noneKnown &&
            allergies.fields.map((row, index) => (
              <div key={row.id}>
                <Controller
                  name={`allergies.${index}.substance`}
                  control={control}
                  render={({ field, fieldState: { error } }) => (
                    <Form.Item label="На что" description={error?.message ? <FieldError message={error.message} /> : fieldNote({ value: field.value, max: 100 })}>
                      <Input {...textProps} value={field.value} onChange={field.onChange} onBlur={field.onBlur} placeholder="Например, курица" maxLength={100} />
                    </Form.Item>
                  )}
                />
                <Controller
                  name={`allergies.${index}.reaction`}
                  control={control}
                  render={({ field }) => (
                    <Form.Item label="Как проявляется" description={fieldNote({ value: field.value, max: 200 })}>
                      <Input {...textProps} value={field.value ?? ''} onChange={field.onChange} onBlur={field.onBlur} placeholder="Зуд, покраснение ушей" maxLength={200} />
                    </Form.Item>
                  )}
                />
                <Form.Item>
                  <Button size="small" color="danger" fill="none" onClick={() => allergies.remove(index)} aria-label={`Убрать аллергию ${index + 1}`}>
                    <DeleteOutline aria-hidden /> Убрать
                  </Button>
                </Form.Item>
              </div>
            ))}
          {!noneKnown && (
            <Form.Item>
              <Button block fill="outline" color="primary" onClick={() => allergies.append({ substance: '', reaction: '' })}>
                + Добавить аллерген
              </Button>
            </Form.Item>
          )}

          <Form.Header>Хронические состояния</Form.Header>
          {conditions.fields.map((row, index) => (
            <div key={row.id}>
              <Controller
                name={`conditions.${index}.name`}
                control={control}
                render={({ field, fieldState: { error } }) => (
                  <Form.Item label="Состояние или диагноз" description={error?.message ? <FieldError message={error.message} /> : fieldNote({ value: field.value, max: 100 })}>
                    <Input {...textProps} value={field.value} onChange={field.onChange} onBlur={field.onBlur} placeholder="Например, хронический гастрит" maxLength={100} />
                  </Form.Item>
                )}
              />
              <Controller
                name={`conditions.${index}.since_year`}
                control={control}
                render={({ field, fieldState: { error } }) => (
                  <Form.Item label="С какого года" description={error?.message ? <FieldError message={error.message} /> : undefined}>
                    <Input
                      {...textProps}
                      value={field.value ?? ''}
                      onChange={(v) => /^\d{0,4}$/.test(v) && field.onChange(v)}
                      onBlur={field.onBlur}
                      inputMode="numeric"
                      placeholder="Необязательно"
                    />
                  </Form.Item>
                )}
              />
              <Controller
                name={`conditions.${index}.note`}
                control={control}
                render={({ field }) => (
                  <Form.Item label="Заметка" description={fieldNote({ value: field.value, max: 300 })}>
                    <Input {...textProps} value={field.value ?? ''} onChange={field.onChange} onBlur={field.onBlur} placeholder="Например, обострения осенью" maxLength={300} />
                  </Form.Item>
                )}
              />
              <Form.Item>
                <Button size="small" color="danger" fill="none" onClick={() => conditions.remove(index)} aria-label={`Убрать состояние ${index + 1}`}>
                  <DeleteOutline aria-hidden /> Убрать
                </Button>
              </Form.Item>
            </div>
          ))}
          <Form.Item>
            <Button block fill="outline" color="primary" onClick={() => conditions.append({ name: '', since_year: '', note: '' })}>
              + Добавить состояние
            </Button>
          </Form.Item>

          <Form.Header>Идентификация</Form.Header>
          <Controller
            name="blood_type"
            control={control}
            render={({ field }) => (
              <Form.Item label="Группа крови" description={fieldNote({ value: field.value, max: 20 })}>
                <Input {...textProps} value={field.value ?? ''} onChange={field.onChange} onBlur={field.onBlur} placeholder="Необязательно" maxLength={20} />
              </Form.Item>
            )}
          />
          <Controller
            name="chip_number"
            control={control}
            render={({ field }) => (
              <Form.Item label="Номер чипа или клейма" description={fieldNote({ value: field.value, max: 30 })}>
                <Input {...textProps} value={field.value ?? ''} onChange={field.onChange} onBlur={field.onBlur} placeholder="Необязательно" maxLength={30} />
              </Form.Item>
            )}
          />

          <span id="medprofile-clinic" />
          <Form.Header>Клиника</Form.Header>
          <Controller
            name="clinic.name"
            control={control}
            render={({ field }) => (
              <Form.Item label="Название">
                <Input {...textProps} value={field.value ?? ''} onChange={field.onChange} onBlur={field.onBlur} placeholder="Где наблюдается" maxLength={100} />
              </Form.Item>
            )}
          />
          <Controller
            name="clinic.vet"
            control={control}
            render={({ field }) => (
              <Form.Item label="Врач">
                <Input {...textProps} value={field.value ?? ''} onChange={field.onChange} onBlur={field.onBlur} placeholder="Необязательно" maxLength={100} />
              </Form.Item>
            )}
          />
          <Controller
            name="clinic.phone"
            control={control}
            render={({ field }) => (
              <Form.Item label="Телефон">
                <Input {...textProps} type="tel" inputMode="tel" autoComplete="off" value={field.value ?? ''} onChange={field.onChange} onBlur={field.onBlur} placeholder="Необязательно" maxLength={30} />
              </Form.Item>
            )}
          />
        </Form>

        {/* A long form: the save button stays in reach above the tab bar, not three screens down. */}
        <div className="form-sticky-action safe-area-padding">
          <SpinnerButton loading={save.isPending || isSubmitting} onClick={() => {
              pruneEmptyRows();
              handleSubmit(onSubmit, onInvalidSubmit)();
            }}>
            Сохранить
          </SpinnerButton>
        </div>
        <div className="safe-area-padding" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)', margin: 'var(--spacing-md) 0 var(--spacing-xl)' }}>
          <Button block size="large" onClick={() => goBack(navigate, cardPath)}>
            Отмена
          </Button>
        </div>
      </div>
      {leaveDialog}
    </div>
  );
}
