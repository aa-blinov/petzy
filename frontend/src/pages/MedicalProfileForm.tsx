import { useEffect, useRef } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useFieldArray, useForm, Controller, useWatch, type Control, type UseFormGetValues } from 'react-hook-form';
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
import { showSnackbar } from '../utils/snackbar';
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
  clinics: z
    .array(
      z.object({
        name: z.string().max(100).optional(),
        phone: z.string().max(30).optional(),
        doctors: z.array(
          z.object({
            name: z.string().trim().min(1, 'Укажите врача').max(100),
            specialty: z.string().max(60).optional(),
          }),
        ),
      }),
    )
    .max(5),
});

type ProfileForm = z.infer<typeof profileSchema>;

const EMPTY: ProfileForm = {
  chip_number: '',
  blood_type: '',
  allergies_none_known: false,
  allergies: [],
  conditions: [],
  clinics: [{ name: '', phone: '', doctors: [] }],
};

const MAX_CLINICS = 5;

/** A button that takes a row away is a real target, not a 27px word next to the field. */
const REMOVE_STYLE = { minHeight: 44, padding: '0 12px' } as React.CSSProperties;

/** Takes a row out of a list and offers to put it back: a filled-in allergy is not lost by one wrong tap. */
function removeWithUndo<T>(list: { remove: (i: number) => void; insert: (i: number, v: T) => void }, index: number, row: T, message: string) {
  list.remove(index);
  showSnackbar({ message, action: { label: 'Отменить', run: () => list.insert(index, row) } });
}
const MAX_DOCTORS = 10;

const textProps = { style: { '--text-align': 'left' } as React.CSSProperties };

/** One clinic: its name and phone, and the doctors seen there with what they do. */
function ClinicBlock({ control, index, only, onRemove, getValues }: { control: Control<ProfileForm>; index: number; only: boolean; onRemove: () => void; getValues: UseFormGetValues<ProfileForm> }) {
  const doctors = useFieldArray({ control, name: `clinics.${index}.doctors` });
  return (
    <div role="group" aria-label={`Клиника ${index + 1}`}>
      {!only && <p style={{ margin: 'var(--spacing-lg) 0 0', padding: '0 var(--spacing-lg)', fontSize: 'var(--text-md)', fontWeight: 700 }}>Клиника {index + 1}</p>}
      <Controller
        name={`clinics.${index}.name`}
        control={control}
        render={({ field }) => (
          <Form.Item label="Название">
            <Input {...textProps} value={field.value ?? ''} onChange={field.onChange} onBlur={field.onBlur} placeholder={index === 0 ? 'Где наблюдается' : 'Название клиники'} maxLength={100} />
          </Form.Item>
        )}
      />
      <Controller
        name={`clinics.${index}.phone`}
        control={control}
        render={({ field }) => (
          <Form.Item label="Телефон">
            <Input {...textProps} type="tel" inputMode="tel" autoComplete="off" value={field.value ?? ''} onChange={field.onChange} onBlur={field.onBlur} placeholder="Необязательно" maxLength={30} />
          </Form.Item>
        )}
      />
      {doctors.fields.map((row, j) => (
        <div key={row.id}>
          <Controller
            name={`clinics.${index}.doctors.${j}.name`}
            control={control}
            render={({ field, fieldState: { error } }) => (
              <Form.Item label="Врач" description={error?.message ? <FieldError message={error.message} /> : undefined}>
                <Input {...textProps} value={field.value} onChange={field.onChange} onBlur={field.onBlur} placeholder="Например, Иванова А. П." maxLength={100} />
              </Form.Item>
            )}
          />
          <Controller
            name={`clinics.${index}.doctors.${j}.specialty`}
            control={control}
            render={({ field }) => (
              <Form.Item label="Специальность">
                <Input {...textProps} value={field.value ?? ''} onChange={field.onChange} onBlur={field.onBlur} placeholder="Терапевт, кардиолог, стоматолог" maxLength={60} />
              </Form.Item>
            )}
          />
          <Form.Item>
            <Button size="small" color="danger" fill="none" style={REMOVE_STYLE} onClick={() => removeWithUndo(doctors, j, getValues().clinics[index].doctors[j], 'Врач убран')} aria-label={`Убрать врача ${j + 1} клиники ${index + 1}`}>
              <DeleteOutline aria-hidden /> Убрать врача
            </Button>
          </Form.Item>
        </div>
      ))}
      {doctors.fields.length < MAX_DOCTORS && (
        <Form.Item>
          <Button block fill="outline" size="small" onClick={() => doctors.append({ name: '', specialty: '' })}>
            + Добавить врача
          </Button>
        </Form.Item>
      )}
      {!only && (
        <Form.Item>
          <Button size="small" color="danger" fill="none" style={REMOVE_STYLE} onClick={onRemove} aria-label={`Убрать клинику ${index + 1}`}>
            <DeleteOutline aria-hidden /> Убрать клинику
          </Button>
        </Form.Item>
      )}
    </div>
  );
}

/** What a vet asks first: allergies, chronic conditions, chip, blood type and the clinics.
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

  const { control, handleSubmit, reset, getValues, formState: { isDirty, isSubmitting } } = useForm<ProfileForm>({
    mode: 'onTouched',
    shouldFocusError: false,
    resolver: zodResolver(profileSchema),
    defaultValues: EMPTY,
  });
  const allergies = useFieldArray({ control, name: 'allergies' });
  const conditions = useFieldArray({ control, name: 'conditions' });
  const clinics = useFieldArray({ control, name: 'clinics' });
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
      clinics: profile.clinics.length
        ? profile.clinics.map((c) => ({ name: c.name ?? '', phone: c.phone ?? '', doctors: c.doctors.map((d) => ({ name: d.name, specialty: d.specialty ?? '' })) }))
        : EMPTY.clinics,
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
        clinics: data.clinics
          .map((c) => ({
            name: c.name?.trim() || null,
            phone: c.phone?.trim() || null,
            doctors: c.doctors.map((d) => ({ name: d.name.trim(), specialty: d.specialty?.trim() || null })),
          }))
          .filter((c) => c.name || c.phone || c.doctors.length),
        clinic: { name: null, vet: null, phone: null },
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
    // A clinic with nothing in it, a doctor with nothing in the row: not entries either.
    const kept = values.clinics
      .map((c) => ({ ...c, doctors: c.doctors.filter((d) => d.name?.trim() || d.specialty?.trim()) }))
      .filter((c) => c.name?.trim() || c.phone?.trim() || c.doctors.length);
    const changed = kept.length !== values.clinics.length || kept.some((c, i) => c.doctors.length !== values.clinics[i]?.doctors.length);
    if (changed) clinics.replace(kept.length ? kept : EMPTY.clinics);
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
                      // The list is put away, not wiped: «no allergies» and a list of them contradict each other, so it is
                      // not saved, and the way back is one tap.
                      if (on && getValues().allergies.some((a) => a.substance?.trim() || a.reaction?.trim())) {
                        showSnackbar({
                          message: 'Список аллергенов не сохранится',
                          action: { label: 'Вернуть', run: () => field.onChange(false) },
                        });
                      }
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
                  <Button size="small" color="danger" fill="none" style={REMOVE_STYLE} onClick={() => removeWithUndo(allergies, index, getValues().allergies[index], 'Аллерген убран')} aria-label={`Убрать аллергию ${index + 1}`}>
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
                <Button size="small" color="danger" fill="none" style={REMOVE_STYLE} onClick={() => removeWithUndo(conditions, index, getValues().conditions[index], 'Состояние убрано')} aria-label={`Убрать состояние ${index + 1}`}>
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

          <Form.Header>Чип и группа крови</Form.Header>
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
          <Form.Header>Клиники и врачи</Form.Header>
          {clinics.fields.map((row, index) => (
            <ClinicBlock key={row.id} control={control} index={index} only={clinics.fields.length === 1} getValues={getValues} onRemove={() => removeWithUndo(clinics, index, getValues().clinics[index], 'Клиника убрана')} />
          ))}
          {clinics.fields.length < MAX_CLINICS && (
            <Form.Item>
              <Button block fill="outline" color="primary" onClick={() => clinics.append({ name: '', phone: '', doctors: [] })}>
                + Добавить клинику
              </Button>
            </Form.Item>
          )}
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
