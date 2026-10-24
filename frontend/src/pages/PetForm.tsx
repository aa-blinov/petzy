import { useEffect, useState, useRef } from 'react';
import { drawableImage } from '../utils/drawableImage';
import { showToast } from '../utils/toast';
import { getApiErrorMessage } from '../utils/apiError';
import { isMissing } from '../utils/notFound';
import { useNavigate, useParams } from 'react-router-dom';
import { goBack } from '../utils/navigation';
import { usePet } from '../hooks/usePet';
import { useSessionDraft } from '../hooks/useSessionDraft';
import { Button, Form, Input, Picker, TextArea, ImageViewer } from 'antd-mobile';
import type { InputRef, TextAreaRef } from 'antd-mobile';
import { Camera } from 'lucide-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useForm, useWatch, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

/** Neutering options; the row's own label says which (see neuteringLabel). */
const NEUTERED_OPTIONS = [
    { label: 'Не указано', value: '' },
    { label: 'Нет', value: 'false' },
    { label: 'Да', value: 'true' },
];

import { petsService, type Pet } from '../services/pets.service';
import { PetSharePanel } from '../components/PetShareSheet';
import { GENDER_OPTIONS } from '../utils/constants';
import { defaultTilesFor, getSpecies, neuteringLabel } from '../utils/species';
import { SpeciesTiles } from '../components/SpeciesTiles';
import { PetAddedSheet } from '../components/PetAddedSheet';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { SpinnerButton } from '../components/SpinnerButton';
import { EmptyState } from '../components/EmptyState';
import { LoadError } from '../components/LoadError';
import { PawPrint } from 'lucide-react';
import { newFormKey } from '../utils/idempotency';
import { PhotoCropModal } from '../components/PhotoCropModal';
import { onInvalidSubmit } from '../utils/formErrors';
import { FormDangerButton } from '../components/FormDangerButton';
import { useDeletePet, useLeavePet } from '../hooks/useDeletePet';
import { PetDeleteSummary } from '../components/PetDeleteSummary';
import { useUnsavedChangesGuard } from '../hooks/useUnsavedChangesGuard';
import { fieldNote } from '../components/FieldNote';
import { FieldError } from '../components/FieldError';
import { DatePickerField } from '../components/DatePickerField';
import { useTypedDateProblems } from '../hooks/useTypedDateProblems';
import { notInFuture, FUTURE_DATE_MESSAGE } from '../utils/birthDate';

const petSchema = z.object({
  name: z.string().trim().min(1, 'Введите имя питомца'),
  breed: z.string().optional(),
  species: z.string().optional(),
  // A pet is not born in the future: said on the field, whether the date was wheeled to or typed.
  birth_date: z.string().optional().refine((v) => notInFuture(v), FUTURE_DATE_MESSAGE),
  gender: z.string().optional(),
  is_neutered: z.boolean().optional(),
  health_notes: z.string().optional(),
});

type PetFormData = z.infer<typeof petSchema>;

interface PetPhotoItem {
  url: string;
  file?: File;
}

export function PetForm() {
  // One key per opening of the form: a retry after a lost answer does not add the pet twice.
  const createKey = useRef(newFormKey());
  const navigate = useNavigate();
  const { selectPet } = usePet();
  const deletePet = useDeletePet();
  const leavePet = useLeavePet();
  const { id } = useParams<{ id: string }>();
  const isEditing = !!id;
  const queryClient = useQueryClient();

  const [fileList, setFileList] = useState<PetPhotoItem[]>([]);
  const [cropTarget, setCropTarget] = useState<{ src: string; filename: string } | null>(null);
  const [loading, setLoading] = useState(false);
  const [neuteredPickerVisible, setNeuteredPickerVisible] = useState(false);
  // A new pet starts with the few things it needs; the rest of the form opens on a tap (an existing pet shows all of it).
  const [showMore, setShowMore] = useState(false);
  // The pet just added: what its «+» starts with and what to do next, before leaving the form.
  const [addedPet, setAddedPet] = useState<Pet | null>(null);
  const [genderPickerVisible, setGenderPickerVisible] = useState(false);

  // State for Image Viewer to avoid imperative ImageViewer.show()
  const [imageViewer, setImageViewer] = useState<{ visible: boolean; image: string | null }>({
    visible: false,
    image: null,
  });

  // Track if form was initialized for this pet to prevent overwriting user changes
  const initializedPetId = useRef<string | null>(null);

  // Refs for focusing inputs on row click
  const nameInputRef = useRef<InputRef>(null);
  const breedInputRef = useRef<InputRef>(null);
  const healthNotesInputRef = useRef<TextAreaRef>(null);

  const { control, handleSubmit, reset, getValues, formState: { isDirty } } = useForm<PetFormData>({
    // onInvalidSubmit scrolls to and focuses the first error in page order;
    // RHF's own focus picked the first registered ref instead.
    // Validated when a field is left, and after that as it changes: an error
    // shows as soon as it is known, not only after «Сохранить».
    mode: 'onTouched',
    shouldFocusError: false,
    resolver: zodResolver(petSchema),
    defaultValues: {
      name: '',
      breed: '',
      birth_date: '',
      gender: '',
      species: '',
      is_neutered: undefined,
      health_notes: '',
    }
  });

  // Fields that depend on the species and gender: what «Порода» is called,
  // and whether (and how) neutering is asked about.
  const speciesValue = useWatch({ control, name: 'species' });
  const genderValue = useWatch({ control, name: 'gender' });
  const species = getSpecies(speciesValue);

  // One pet by its own address, not the whole roster and a search through it: opening the form
  // used to pull every pet the person has. The roster is the cache this is seeded from, so the
  // form opens filled at once and the request by address is what refreshes it.
  const { data: pet, isLoading: isLoadingPet, isError: petFailed, error: petError, refetch: refetchPet } = useQuery({
    queryKey: ['pet', id],
    queryFn: async () => (id ? await petsService.getPet(id) : null),
    enabled: isEditing && !!id,
    initialData: () => {
      if (!id) return undefined;
      const cached = queryClient.getQueryData<Pet[]>(['pets'])?.find((p) => p._id === id);
      return cached ?? undefined;
    },
  });
  // Someone it is shared with sees the card but cannot change it (the server refuses): so the screen does not offer to.
  const readOnly = isEditing && !!pet && !pet.current_user_is_owner;

  // Anything typed, or a photo picked or removed, is unsaved until «Сохранить». Sharing is not part of it: an invitation
  // goes out at once, on its own «Пригласить» (components/PetShareSheet.tsx).
  const photoChanged = fileList[0]?.file instanceof File || (fileList.length === 0 && !!pet?.photo_url);
  const { dialog: leaveDialog, release } = useUnsavedChangesGuard(isDirty || photoChanged);

  useEffect(() => {
    if (pet && initializedPetId.current !== pet._id) {
      // Only initialize once per pet to prevent overwriting user changes
      initializedPetId.current = pet._id;
      reset({
        name: pet.name,
        breed: pet.breed || '',
        birth_date: pet.birth_date || '',
        gender: pet.gender || '',
        // Hand-typed species from before the picker («Кот») map to their key.
        species: pet.species ? (getSpecies(pet.species).key !== 'other' ? getSpecies(pet.species).key : pet.species) : '',
        is_neutered: pet.is_neutered ?? undefined,
        health_notes: pet.health_notes || '',
      });
      if (pet.photo_url) {
        setFileList([{ url: pet.photo_url }]);
      } else {
        setFileList([]);
      }
    } else if (!isEditing) {
      reset({
        name: '',
        breed: '',
        birth_date: '',
        gender: '',
        species: '',
        is_neutered: undefined,
        health_notes: '',
      });
      setFileList([]);
    }
  }, [pet, isEditing, reset]);
  // The typed fields come back after a session that ran out (the photo and the sharing do not).
  // Нового питомца ещё нет: у такой формы своего питомца нет, и черновик адресован только пути /pets/new.
  useSessionDraft({ dirty: isDirty, petId: pet?._id ?? null, getValues, reset, ready: !isEditing || !!pet, release });

  // A typed date that is unfinished or impossible is not in the form's value: saving would keep the older one in silence.
  const typedDates = useTypedDateProblems();
  const submit = () => {
    typedDates.refuse();
    void handleSubmit((values) => (typedDates.blocked ? undefined : onSubmit(values)), onInvalidSubmit)();
  };

  const onSubmit = async (values: PetFormData) => {
    try {
      setLoading(true);
      const hasNewFile = fileList[0]?.file instanceof File;
      const photoWasRemoved = fileList.length === 0 && !!pet?.photo_url;

      const petData = {
        ...values,
        photo_file: hasNewFile ? fileList[0].file : undefined,
        // Don't send photo_url for new files (blob URL) - only send when no change needed
        photo_url: undefined,
        remove_photo: photoWasRemoved ? true : undefined,
      };

      let petId = id;
      let createdPet: Pet | undefined;
      if (isEditing && id) {
        await petsService.updatePet(id, petData);
      } else {
        // A new pet starts with the events that make sense for its species
        // (no litter or tooth brushing for a fish); all can be turned on later.
        const newPet = await petsService.createPet({ ...petData, tiles_settings: defaultTilesFor(values.species) }, createKey.current);
        createKey.current = newFormKey();
        petId = newPet._id;
        createdPet = newPet;
      }

      // Invalidate cache BEFORE navigating to ensure fresh data
      await queryClient.invalidateQueries({ queryKey: ['pets'] });
      if (petId) {
        await queryClient.invalidateQueries({ queryKey: ['pet', petId] });
      }

      // The pet just added is the one the person is about to write about: it is the selected one from here on, as it is after onboarding.
      if (createdPet) selectPet(createdPet);

      release();
      if (createdPet) {
        // A new pet is greeted and offered what to do next; leaving the sheet leaves the form.
        setAddedPet(createdPet);
        return;
      }
      // Leave at once; the toast lives on over the list.
      showToast.success('Питомец сохранён');
      goBack(navigate, '/pets');
    } catch (error) {
      const errorMessage = getApiErrorMessage(error, 'Не удалось сохранить');
      showToast.failure(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  if (isEditing && isLoadingPet) {
    return <LoadingSpinner />;
  }
  // An address of a pet that is not there, or not the person's: said so, not an empty form to fill in. A failed
  // request is not that: it never got an answer, so the screen offers to ask again.
  const petGone = isMissing(petError);
  if (isEditing && !pet && petFailed && !petGone) {
    return (
      <div className="page-container">
        <div className="max-width-container">
          <LoadError what="питомца" onRetry={refetchPet} />
        </div>
      </div>
    );
  }
  if (isEditing && !pet) {
    return (
      <div className="page-container">
        <div className="max-width-container">
          <EmptyState
            icon={PawPrint}
            title="Питомец не найден"
            description="Возможно, его удалили или закрыли вам доступ"
            actionLabel="К питомцам"
            onAction={() => navigate('/pets', { replace: true })}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="page-container">
      <div className="max-width-container">
        <div className="safe-area-padding" style={{
          marginBottom: readOnly ? 0 : 'var(--spacing-lg)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}>
          <div className="screen-head">
            <h1 className="screen-title" style={{ fontSize: 'var(--text-xxl)', fontWeight: 600, margin: 0 }}>
              {isEditing ? 'Изменить питомца' : 'Новый питомец'}
            </h1>
          </div>
        </div>

        {/* 4px under the title: this note is the line the title is about, and it carries the
            room before the form. The title block's own margin is that room only without it. */}
        {readOnly && (
          <p className="safe-area-padding" role="note" style={{ margin: 'var(--spacing-xs) 0 var(--spacing-md)', color: 'var(--app-text-secondary)' }}>
            Карточку питомца меняет владелец. Вам можно смотреть её и добавлять записи, а когда питомец больше не нужен, выйти из доступа
          </p>
        )}
        {/* inert: nothing in a card that cannot be saved takes focus or a tap. */}
        <div {...(readOnly ? { inert: '' } : {})} style={readOnly ? { opacity: 0.7 } : undefined}>
          <Form
            layout="horizontal"
            mode="card"
            style={{
              // Wider than the other forms' 7em: «Дата рождения» fits on one line.
              '--prefix-width': '8em'
            } as React.CSSProperties}
          >
            <Form.Header>О питомце</Form.Header>
            <Controller
              name="species"
              control={control}
              render={({ field }) => (
                <Form.Item label="Вид питомца" layout="vertical">
                  <SpeciesTiles value={field.value} onChange={field.onChange} />
                </Form.Item>
              )}
            />

            <Controller
              name="name"
              control={control}
              render={({ field, fieldState: { error } }) => (
                <Form.Item
                  label="Имя"
                  required
                  description={fieldNote({ error: error?.message, value: field.value, max: 100 })}
                  clickable
                  // A text field, not a picker: no «›» promising another screen.
                  arrow={false}
                  onClick={() => nameInputRef.current?.focus()}
                >
                  <Input
                    {...field}
                    ref={nameInputRef}
                    maxLength={100}
                    id="name"
                    placeholder="Имя питомца"
                  />
                </Form.Item>
              )}
            />

            <Form.Item label="Фото" layout="vertical">
              <input
                type="file"
                accept="image/*"
                id="pet-photo-input"
                // Visually hidden, not display:none: the input stays in
                // the Tab order, so the picker opens from the keyboard.
                className="sr-only file-picker-input"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  e.target.value = '';
                  if (!file) return;
                  // A HEIC that this browser cannot draw is made drawable first (utils/drawableImage).
                  drawableImage(file, () => showToast.info('Готовим фото'))
                    .then((picture) => setCropTarget({ src: URL.createObjectURL(picture), filename: file.name }))
                    .catch(() => showToast.failure('Не удалось открыть фото. Попробуйте другой снимок'));
                }}
              />

              {fileList.length > 0 && fileList[0]?.url ? (
                // Photo exists - show photo card with overlay actions
                <div
                  style={{
                    position: 'relative',
                    width: '120px',
                    height: '120px',
                    borderRadius: 'var(--radius-md)',
                    overflow: 'hidden',
                    boxShadow: 'var(--app-shadow)',
                  }}
                >
                  <img
                    src={fileList[0].url}
                    alt="Фото питомца"
                    style={{
                      width: '100%',
                      height: '100%',
                      objectFit: 'cover',
                      cursor: 'pointer',
                    }}
                    onClick={() => setImageViewer({ visible: true, image: fileList[0].url })}
                  />
                  {/* Overlay with actions */}
                  <div
                    style={{
                      position: 'absolute',
                      bottom: 0,
                      left: 0,
                      right: 0,
                      display: 'flex',
                      justifyContent: 'center',
                      gap: '8px',
                      padding: '8px',
                      background: 'linear-gradient(transparent, var(--app-scrim-strong))',
                    }}
                  >
                    <button
                      type="button"
                      onClick={() => document.getElementById('pet-photo-input')?.click()}
                      style={{
                        width: '32px',
                        height: '32px',
                        borderRadius: '50%',
                        border: 'none',
                        background: 'var(--app-white-90)',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: 'var(--text-md)',
                      }}
                      title="Заменить фото"
                      className="touch-target"
                    >
                      <Camera size={16} strokeWidth={2} style={{ display: 'block' }} />
                    </button>
                    <button
                      type="button"
                      onClick={() => setFileList([])}
                      style={{
                        width: '32px',
                        height: '32px',
                        borderRadius: '50%',
                        border: 'none',
                        background: 'var(--app-danger-color)',
                        color: 'var(--app-text-on-dark)',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: 'var(--text-md)',
                        fontWeight: 'bold',
                      }}
                      aria-label="Удалить фото"
                      className="touch-target"
                    >
                      <span aria-hidden>×</span>
                    </button>
                  </div>
                </div>
              ) : (
                // No photo - show upload zone. Wrapped in <label htmlFor="pet-photo-input">
                // so keyboard / screen-reader users get the same affordance
                // as mouse users — clicking the dashed zone opens the file
                // picker just like clicking the hidden <input>.
                <label htmlFor="pet-photo-input" className="photo-upload-zone">
                  <Camera size={32} strokeWidth={1.5} style={{ display: 'block', opacity: 0.6 }} />
                  <span style={{
                    fontSize: 'var(--text-xs)',
                    color: 'var(--adm-color-text-secondary)',
                    textAlign: 'center'
                  }}>
                    Выбрать фото
                  </span>
                </label>
              )}
            </Form.Item>
            {/* A new pet needs a name and a kind; the rest can be told later, so it is one tap away and not the whole form. */}
            {!isEditing && !showMore && (
              <Form.Item
                clickable
                arrow
                onClick={() => setShowMore(true)}
                description="Порода, дата рождения, пол, заметки о здоровье"
              >
                Ещё о питомце
              </Form.Item>
            )}
            {(isEditing || showMore) && (
              <>
            <Controller
              name="breed"
              control={control}
              render={({ field }) => (
                <Form.Item
                  label={species.breedLabel}
                  description={fieldNote({ value: field.value, max: 100 })}
                  clickable
                  arrow={false}
                  onClick={() => breedInputRef.current?.focus()}
                >
                  <Input
                    {...field}
                    ref={breedInputRef}
                    maxLength={100}
                    id="breed"
                    placeholder={speciesValue ? species.breedPlaceholder : 'Необязательно'}
                  />
                </Form.Item>
              )}
            />

            <Controller
              name="birth_date"
              control={control}
              render={({ field, fieldState: { error } }) => (
                <DatePickerField
                  id="birth_date"
                  label="Дата рождения"
                  value={field.value ?? ''}
                  onChange={field.onChange}
                  onBlur={field.onBlur}
                  onTypedProblem={typedDates.report('birth_date')}
                  refusals={typedDates.refusals}
                  // The same 50 years back as the onboarding step; a pet is not born in the future.
                  yearsBack={50}
                  yearsForward={0}
                  clearLabel="Убрать дату рождения"
                  placeholder="Не указано"
                  description={error?.message ? <FieldError message={error.message} /> : undefined}
                />
              )}
            />

            <Controller
              name="gender"
              control={control}
              render={({ field }) => {
                const selectedLabel = GENDER_OPTIONS.find(o => o.value === (field.value || ''))?.label || '';
                return (
                  <Form.Item
                    label="Пол"
                    clickable
                    arrow
                    onClick={() => setGenderPickerVisible(true)}
                  >
                    <span style={{ color: field.value ? 'var(--app-text-primary)' : 'var(--app-text-tertiary)' }}>
                      {selectedLabel || 'Не указан'}
                    </span>
                    <Picker
                      columns={[GENDER_OPTIONS]}
                      visible={genderPickerVisible}
                      value={field.value ? [field.value] : ['']}
                      onClose={() => setGenderPickerVisible(false)}
                      onConfirm={(val) => {
                        field.onChange(val[0] as string);
                        setGenderPickerVisible(false);
                      }}
                      cancelText="Отмена"
                      confirmText="Готово"
                    />
                  </Form.Item>
                );
              }}
            />

            {/* Mammals only: no neutering row for a bird, fish or reptile. */}
            {species.neutering && (
            <Controller
              name="is_neutered"
              control={control}
              render={({ field: { value, onChange } }) => {
                // Display label: handle the undefined case so it doesn't
                // show 'Нет' by default for an unset optional field.
                const displayValue = value === undefined ? '' : String(value);
                const selectedLabel = NEUTERED_OPTIONS.find(o => o.value === displayValue)?.label || '';
                return (
                  <Form.Item
                    label={neuteringLabel(genderValue)}
                    clickable
                    arrow
                    onClick={() => setNeuteredPickerVisible(true)}
                  >
                    <span style={{ color: value !== undefined ? 'var(--app-text-primary)' : 'var(--app-text-tertiary)' }}>
                      {selectedLabel || 'Не указано'}
                    </span>
                    <Picker
                      columns={[NEUTERED_OPTIONS]}
                      visible={neuteredPickerVisible}
                      value={[displayValue]}
                      onClose={() => setNeuteredPickerVisible(false)}
                      onConfirm={(val) => {
                        const v = val[0] as string;
                        if (v === '') onChange(undefined);
                        else onChange(v === 'true');
                        setNeuteredPickerVisible(false);
                      }}
                      cancelText="Отмена"
                      confirmText="Готово"
                    />
                  </Form.Item>
                );
              }}
            />
            )}
            <Controller
              name="health_notes"
              control={control}
              render={({ field }) => (
                <Form.Item
                  label="Заметки о здоровье"
                  layout="vertical"
                  description={fieldNote({
                    value: field.value,
                    max: 1000,
                    always: true,
                    hint: isEditing ? 'Аллергии, хронические состояния и прививки вносятся в медкарте' : undefined,
                  })}
                >
                  <TextArea
                    {...field}
                    ref={healthNotesInputRef}
                    maxLength={1000}
                    placeholder="Важная информация о здоровье"
                    autoSize={{ minRows: 2, maxRows: 5 }}
                  />
                </Form.Item>
              )}
            />

              </>
            )}
          </Form>

          {/* Sharing is an owner-only capability: the backend already rejects a non-owner's attempt to add or remove access,
              and a shared user is not shown who else has it. A new pet has no owner yet, so the section waits for it.
              The same piece as the «Поделиться» sheet of the feed and of the list of pets: its own «Пригласить» sends the
              invitation at once, «Сохранить» below is for the card. */}
          {isEditing && pet?.current_user_is_owner && (
            <section aria-label="Поделиться доступом" style={{ marginTop: 'var(--spacing-lg)' }}>
              <h2 className="section-header" style={{ marginBottom: 'var(--spacing-sm)' }}>Поделиться доступом</h2>
              <div className="card-soft" style={{ padding: 'var(--spacing-md)' }}>
                <PetSharePanel pet={pet} />
                <p style={{ margin: 'var(--spacing-md) 4px 0', fontSize: 'var(--text-sm)', color: 'var(--app-text-secondary)' }}>
                  Приглашение уходит сразу, по кнопке «Пригласить»: «Сохранить» для него не нужно
                </p>
              </div>
            </section>
          )}
        </div>

        {/* Outside the wrapper above: the row into the pet's events and the buttons are the
            way out for someone the pet is shared with, and a dimmed card may not take a tap. */}
        {isEditing && id && pet && (
          // One place for the pet's events: its own screen. This row takes the person there for this pet.
          <Form layout="horizontal" mode="card">
            <Form.Item
              label="Типы записей питомца"
              description="Какие записи предлагает «+» и в каком порядке"
              clickable
              arrow
              onClick={() => {
                selectPet(pet);
                navigate('/pet-events');
              }}
            />
          </Form>
        )}



          {/* A long form: the main button stays above the tab bar, not three screens down. */}
          {!readOnly && (
            <div className="form-sticky-action safe-area-padding">
              <button
                style={{ display: 'none' }}
                type="submit"
                onClick={(e) => { e.preventDefault(); submit(); }}
              />
              <SpinnerButton loading={loading} onClick={submit}>
                {isEditing ? 'Сохранить' : 'Добавить'}
              </SpinnerButton>
            </div>
          )}
          <div className="safe-area-padding form-actions" style={{ paddingBottom: 'var(--spacing-xl)' }}>
            <Button
              block
              size="large"
              onClick={() => goBack(navigate, '/pets')}
            >
              {readOnly ? 'Назад' : 'Отмена'}
            </Button>
            {/* Only the owner can delete; the backend refuses anyone else. */}
            {isEditing && pet?.current_user_is_owner && (
              <FormDangerButton
                label="Удалить питомца"
                confirmTitle="Удаление питомца"
                confirmContent={<PetDeleteSummary pet={pet} />}
                onConfirm={async () => {
                  await deletePet(pet);
                  release();
                  // In the app, not back in history: see HealthRecordForm. The «Отменить» bar must outlive this screen.
                  navigate('/pets', { replace: true });
                }}
              />
            )}
            {isEditing && pet && !pet.current_user_is_owner && (
              <FormDangerButton
                label="Выйти из доступа"
                confirmTitle="Выйти из доступа"
                confirmContent={`Больше не видеть «${pet.name}»? Его записи останутся у владельца, он сможет пригласить вас снова`}
                onConfirm={async () => {
                  await leavePet(pet);
                  release();
                  navigate('/pets', { replace: true });
                }}
              />
            )}
          </div>
      </div>
      <ImageViewer
        image={imageViewer.image || ''}
        visible={imageViewer.visible}
        onClose={() => setImageViewer(prev => ({ ...prev, visible: false }))}
        afterClose={() => setImageViewer({ visible: false, image: null })}
      />
      {cropTarget && (
        <PhotoCropModal
          imageSrc={cropTarget.src}
          filename={cropTarget.filename}
          onCancel={() => {
            URL.revokeObjectURL(cropTarget.src);
            setCropTarget(null);
          }}
          onCropped={(file) => {
            setFileList([{ url: URL.createObjectURL(file), file }]);
            URL.revokeObjectURL(cropTarget.src);
            setCropTarget(null);
          }}
        />
      )}
      {leaveDialog}
      <PetAddedSheet
        visible={!!addedPet}
        pet={addedPet}
        onClose={() => goBack(navigate, '/pets')}
        onRecord={(key) => {
          navigate('/', { replace: true });
          navigate(`/form/${key}`);
        }}
        onLook={() => {
          navigate('/', { replace: true });
          navigate('/pet-look');
        }}
      />
    </div>
  );
}
