import { useEffect, useRef } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useFieldArray, useForm, Controller, useWatch, type Control, type UseFormGetValues } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { isAxiosError } from 'axios';
import { Button, Dialog, Form, Input, Switch } from 'antd-mobile';
import { DeleteOutline } from 'antd-mobile-icons';
import { FileHeart } from 'lucide-react';
import { medicalCardService, type MedicalProfile } from '../services/medicalCard.service';
import { EmptyState } from '../components/EmptyState';
import { LoadError } from '../components/LoadError';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { SpinnerButton } from '../components/SpinnerButton';
import { FieldError } from '../components/FieldError';
import { fieldNote } from '../components/FieldNote';
import { httpStatus } from '../services/api';
import { usePet } from '../hooks/usePet';
import { useSessionDraft } from '../hooks/useSessionDraft';
import { useUnsavedChangesGuard } from '../hooks/useUnsavedChangesGuard';
import { onInvalidSubmit } from '../utils/formErrors';
import { goBack } from '../utils/navigation';
import { showToast } from '../utils/toast';
import { showSnackbar } from '../utils/snackbar';
import { confirmWithProgress } from '../utils/medicalReadiness';
import { getApiErrorMessage } from '../utils/apiError';
import { ChoiceChip, ChoiceChips } from '../components/ChoiceChips';
import './MedicalCard.css';

const currentYear = new Date().getFullYear();

const profileSchema = z.object({
  chip_number: z.string().max(30).optional(),
  blood_type: z.string().max(20).optional(),
  diet: z.string().max(200).optional(),
  living: z.string().max(200).optional(),
  reproduction: z.string().max(200).optional(),
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
  diet: '',
  living: '',
  reproduction: '',
  allergies_none_known: false,
  allergies: [],
  conditions: [],
  clinics: [{ name: '', phone: '', doctors: [] }],
};

const MAX_CLINICS = 5;

const DIET_CHIPS = ['Сухой корм', 'Влажный корм', 'Натуральное', 'Смешанное'];
const LIVING_CHIPS = ['Квартира', 'Частный дом, выгул', 'Живёт на улице', 'Есть другие животные'];

/** Taps instead of typing: a chip puts its words in the field, or adds them after what is there. A chip whose words
    are already in the field takes nothing away: the text is the person's. */
function SuggestionChips({ ariaLabel, options, value, onPick }: { ariaLabel: string; options: string[]; value: string; onPick: (next: string) => void }) {
  return (
    <ChoiceChips label={ariaLabel}>
      {options.map((option) => {
        const used = value.toLowerCase().includes(option.toLowerCase());
        return (
          <ChoiceChip key={option} pressed={used} onClick={() => !used && onPick(value.trim() ? `${value.trim().replace(/[,.]$/, '')}, ${option.toLowerCase()}` : option)}>
            {option}
          </ChoiceChip>
        );
      })}
    </ChoiceChips>
  );
}

/** A button that takes a row away is a real target, not a 27px word next to the field. */
const REMOVE_STYLE = { minHeight: 'var(--touch-min)', padding: '0 12px' } as React.CSSProperties;

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
          <Button block fill="outline" color="primary" style={{ minHeight: 'var(--touch-min)' }} onClick={() => doctors.append({ name: '', specialty: '' })}>
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

function profileToForm(profile: MedicalProfile): ProfileForm {
  return {
    chip_number: profile.chip_number ?? '',
    blood_type: profile.blood_type ?? '',
    diet: profile.diet ?? '',
    living: profile.living ?? '',
    reproduction: profile.reproduction ?? '',
    allergies_none_known: profile.allergies_none_known,
    allergies: profile.allergies.map((a) => ({ substance: a.substance, reaction: a.reaction ?? '' })),
    conditions: profile.conditions.map((c) => ({ name: c.name, since_year: c.since_year ? String(c.since_year) : '', note: c.note ?? '' })),
    clinics: profile.clinics.length
      ? profile.clinics.map((c) => ({ name: c.name ?? '', phone: c.phone ?? '', doctors: c.doctors.map((d) => ({ name: d.name, specialty: d.specialty ?? '' })) }))
      : EMPTY.clinics,
  };
}

/** What a vet asks first: allergies, chronic conditions, chip, blood type and the clinics.
    Kept on the pet and open to everyone who has access to it, like the weight. */
/** The parts of the form a link can open at (`?section=`): where it scrolls to and which field takes the cursor. */
const PROFILE_SECTIONS: Record<string, { anchor: string; focus?: string }> = {
  clinic: { anchor: 'medprofile-clinic', focus: 'input[placeholder="Где наблюдается"]' },
  allergies: { anchor: 'medprofile-allergies', focus: 'input[placeholder="Например, курица"]' },
  conditions: { anchor: 'medprofile-conditions', focus: 'input[placeholder="Например, хронический гастрит"]' },
  id: { anchor: 'medprofile-id', focus: 'input[placeholder="Необязательно"][maxlength="20"]' },
  life: { anchor: 'medprofile-life', focus: 'input[placeholder="Например, сухой корм, два раза в день"]' },
};

export function MedicalProfileForm() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const cardPath = `/pets/${id}/medical-card`;
  const { pets, selectedPetId, selectPet } = usePet();
  // The same as the card: the address of another pet makes that pet the chosen one, so the switcher at the top is not lying.
  useEffect(() => {
    const target = pets.find((p) => p._id === id);
    if (target && target._id !== selectedPetId) selectPet(target);
  }, [id, pets, selectedPetId, selectPet]);

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

  // The version the form was made from: the server refuses a save from an older one (someone else saved since).
  const baseVersion = useRef<string | null>(null);
  // The saved profile goes into the form once, when it arrives.
  const loaded = useRef(false);
  const section = useSearchParams()[0].get('section');
  useEffect(() => {
    const profile = query.data?.profile;
    if (!profile || loaded.current) return;
    loaded.current = true;
    // Opened from a link that names a part of the form («Указать клинику», «Аллергия» in «Записать»): the form starts there,
    // with the cursor in the first field, and with an empty row ready where the part is a list that has none yet.
    const target = section ? PROFILE_SECTIONS[section] : undefined;
    if (target) {
      window.setTimeout(() => {
        if (section === 'allergies' && !profile.allergies_none_known && profile.allergies.length === 0) allergies.append({ substance: '', reaction: '' });
        if (section === 'conditions' && profile.conditions.length === 0) conditions.append({ name: '', since_year: '', note: '' });
        window.setTimeout(() => {
          document.getElementById(target.anchor)?.scrollIntoView({ block: 'start' });
          if (target.focus) document.querySelector<HTMLInputElement>(target.focus)?.focus({ preventScroll: true });
        }, 60);
      }, 80);
    }
    baseVersion.current = profile.version ?? null;
    reset(profileToForm(profile));
  }, [query.data, reset, section, allergies, conditions]);
  useSessionDraft({ dirty: isDirty, petId: id ?? null, getValues, reset, ready: !!query.data?.profile, release });

  const save = useMutation({
    mutationFn: (data: ProfileForm) =>
      medicalCardService.saveProfile(id!, {
        chip_number: data.chip_number?.trim() || null,
        blood_type: data.blood_type?.trim() || null,
        diet: data.diet?.trim() || null,
        living: data.living?.trim() || null,
        reproduction: data.reproduction?.trim() || null,
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
        // The legacy single clinic is not sent: the server keeps `clinics` as the truth and fills the old field itself.
        base_version: baseVersion.current ?? "",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['medical-card', id] });
      queryClient.invalidateQueries({ queryKey: ['pets'] });
      void confirmWithProgress(queryClient, id!, 'Данные для врача сохранены');
      release();
      goBack(navigate, cardPath);
    },
    onError: (err: unknown) => {
      const current = isAxiosError(err) && err.response?.status === 409 ? (err.response.data as { profile?: MedicalProfile } | undefined)?.profile : undefined;
      if (current) {
        void resolveConflict(current);
        return;
      }
      showToast.failure(getApiErrorMessage(err, 'Не удалось сохранить'));
    },
  });

  // Someone else saved the profile while this form was open. Saving over it would wipe what they entered: say so,
  // and let the person look at what is there now, or knowingly keep their own version.
  const resolveConflict = async (current: MedicalProfile) => {
    const showCurrent = await Dialog.confirm({
      title: 'Профиль изменили',
      content: 'Пока вы правили, другой человек сохранил профиль. Показать, что там сейчас? Ваши правки в этой форме тогда не сохранятся',
      confirmText: 'Показать актуальный',
      cancelText: 'Сохранить моё',
    });
    baseVersion.current = current.version ?? null;
    if (showCurrent) {
      reset(profileToForm(current));
      queryClient.invalidateQueries({ queryKey: ['medical-card', id] });
      showToast.info('Показали актуальный профиль. Внесите правки ещё раз');
    } else {
      save.mutate(getValues());
    }
  };

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
    // A pet that is gone and a screen that did not load are different: one asks the person to go back to the list,
    // the other to try once more.
    const gone = [403, 404].includes(httpStatus(query.error) ?? 0);
    return (
      <div className="page-container">
        <div className="max-width-container safe-area-padding">
          {gone ? (
            <EmptyState icon={FileHeart} title="Питомец не найден" description="Возможно, его удалили или закрыли вам доступ" actionLabel="К питомцам" onAction={() => navigate('/pets', { replace: true })} />
          ) : (
            <LoadError what="данные для врача" onRetry={() => query.refetch()} />
          )}
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
          <span id="medprofile-allergies" />
          <Form.Header>Аллергии</Form.Header>
          <Controller
            name="allergies_none_known"
            control={control}
            render={({ field }) => (
              <Form.Item
                layout="horizontal"
                label="Аллергий нет"
                description="Включите, если аллергий нет: врач увидит «не выявлено», а не «не указаны»"
                extra={
                  <Switch
                    aria-label="Аллергий нет"
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
              <Button block fill="outline" color="primary" style={{ minHeight: 'var(--touch-min)' }} onClick={() => allergies.append({ substance: '', reaction: '' })}>
                + Добавить аллерген
              </Button>
            </Form.Item>
          )}

          <span id="medprofile-conditions" />
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
            <Button block fill="outline" color="primary" style={{ minHeight: 'var(--touch-min)' }} onClick={() => conditions.append({ name: '', since_year: '', note: '' })}>
              + Добавить состояние
            </Button>
          </Form.Item>

          <span id="medprofile-id" />
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

          <span id="medprofile-life" />
          <Form.Header>Питание и условия жизни</Form.Header>
          <Controller
            name="diet"
            control={control}
            render={({ field }) => (
              <Form.Item label="Чем кормят" description={fieldNote({ value: field.value, max: 200 })}>
                <Input {...textProps} value={field.value ?? ''} onChange={field.onChange} onBlur={field.onBlur} placeholder="Например, сухой корм, два раза в день" maxLength={200} />
                <SuggestionChips ariaLabel="Чем кормят, подсказки" options={DIET_CHIPS} value={field.value ?? ''} onPick={field.onChange} />
              </Form.Item>
            )}
          />
          <Controller
            name="living"
            control={control}
            render={({ field }) => (
              <Form.Item label="Условия жизни" description={fieldNote({ value: field.value, max: 200 })}>
                <Input {...textProps} value={field.value ?? ''} onChange={field.onChange} onBlur={field.onBlur} placeholder="Например, квартира, живёт с собакой" maxLength={200} />
                <SuggestionChips ariaLabel="Условия жизни, подсказки" options={LIVING_CHIPS} value={field.value ?? ''} onPick={field.onChange} />
              </Form.Item>
            )}
          />
          <Controller
            name="reproduction"
            control={control}
            render={({ field }) => (
              <Form.Item label="Репродуктивный статус" description={fieldNote({ value: field.value, max: 200 })}>
                <Input {...textProps} value={field.value ?? ''} onChange={field.onChange} onBlur={field.onBlur} placeholder="Необязательно: беременности, роды, течка" maxLength={200} />
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
              <Button block fill="outline" color="primary" style={{ minHeight: 'var(--touch-min)' }} onClick={() => clinics.append({ name: '', phone: '', doctors: [] })}>
                + Добавить клинику
              </Button>
            </Form.Item>
          )}
          {/* The cap is the server's too: the button that would add a sixth one says nothing, so the limit is said here. */}
          {clinics.fields.length >= MAX_CLINICS && (
            <p className="medcard__empty">Больше пяти клиник добавить нельзя, лишние уберите</p>
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
        <div className="safe-area-padding form-actions">
          <Button block size="large" onClick={() => goBack(navigate, cardPath)}>
            Отмена
          </Button>
        </div>
      </div>
      {leaveDialog}
    </div>
  );
}
