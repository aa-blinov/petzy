import { useEffect, useMemo, useState, useRef } from 'react';
import { parseRecordDate } from '../utils/relativeTime';
import { showToast } from '../utils/toast';
import { getApiErrorMessage } from '../utils/apiError';
import { useNavigate, useParams } from 'react-router-dom';
import { goBack } from '../utils/navigation';
import { usePet } from '../hooks/usePet';
import { useSessionDraft } from '../hooks/useSessionDraft';
import { Button, Dialog, Form, Input, Picker, TextArea, SearchBar, ImageViewer } from 'antd-mobile';
import type { InputRef, TextAreaRef } from 'antd-mobile';
import { UserAddOutline, DeleteOutline } from 'antd-mobile-icons';
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
import { usersService } from '../services/users.service';
import { UserAvatar } from '../components/UserAvatar';
import { GENDER_OPTIONS } from '../utils/constants';
import { defaultTilesFor, getSpecies, neuteringLabel } from '../utils/species';
import { SpeciesTiles } from '../components/SpeciesTiles';
import { PetAddedSheet } from '../components/PetAddedSheet';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { SpinnerButton } from '../components/SpinnerButton';
import { EmptyState } from '../components/EmptyState';
import { PawPrint } from 'lucide-react';
import { PhotoCropModal } from '../components/PhotoCropModal';
import { onInvalidSubmit } from '../utils/formErrors';
import { FormDangerButton } from '../components/FormDangerButton';
import { useDeletePet, useLeavePet } from '../hooks/useDeletePet';
import { PetDeleteSummary } from '../components/PetDeleteSummary';
import { showUndo } from '../utils/undo';
import { useUnsavedChangesGuard } from '../hooks/useUnsavedChangesGuard';
import { fieldNote } from '../components/FieldNote';
import { PickerValue } from '../components/PickerValue';

const petSchema = z.object({
  name: z.string().trim().min(1, 'Введите имя питомца'),
  breed: z.string().optional(),
  species: z.string().optional(),
  birth_date: z.string().optional(),
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
  const [datePickerVisible, setDatePickerVisible] = useState(false);
  const [neuteredPickerVisible, setNeuteredPickerVisible] = useState(false);
  // A new pet starts with the few things it needs; the rest of the form opens on a tap (an existing pet shows all of it).
  const [showMore, setShowMore] = useState(false);
  // The pet just added: what its «+» starts with and what to do next, before leaving the form.
  const [addedPet, setAddedPet] = useState<Pet | null>(null);
  const [genderPickerVisible, setGenderPickerVisible] = useState(false);
  const [internalPickerDate, setInternalPickerDate] = useState<string[]>([]);

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

  const { control, handleSubmit, reset, watch, getValues, formState: { isDirty } } = useForm<PetFormData>({
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

  const [searchTerm, setSearchTerm] = useState('');
  const [searchResults, setSearchResults] = useState<{ username: string }[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);

  const [localSharedWith, setLocalSharedWith] = useState<string[]>([]);

  const birthDateValue = watch('birth_date');
  // Fields that depend on the species and gender: what «Порода» is called,
  // and whether (and how) neutering is asked about.
  const speciesValue = useWatch({ control, name: 'species' });
  const genderValue = useWatch({ control, name: 'gender' });
  const species = getSpecies(speciesValue);

  const { data: pet, isLoading: isLoadingPet } = useQuery({
    queryKey: ['pets', id],
    queryFn: async () => {
      if (!id) return null;
      const pets = await petsService.getPets();
      return pets.find(p => p._id === id) || null;
    },
    enabled: isEditing && !!id,
  });
  // Someone it is shared with sees the card but cannot change it (the server refuses): so the screen does not offer to.
  const readOnly = isEditing && !!pet && !pet.current_user_is_owner;

  // Anything typed, a photo picked or removed, or a change to who has access
  // is unsaved until «Сохранить».
  const sharedBefore = [...(pet?.shared_with || []), ...(pet?.share_invites || [])];
  const sharingChanged =
    localSharedWith.length !== sharedBefore.length || localSharedWith.some(u => !sharedBefore.includes(u));
  const photoChanged = fileList[0]?.file instanceof File || (fileList.length === 0 && !!pet?.photo_url);
  const { dialog: leaveDialog, release } = useUnsavedChangesGuard(isDirty || sharingChanged || photoChanged);

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
      // Members and people invited but not yet answered, in one list.
      setLocalSharedWith([...(pet.shared_with || []), ...(pet.share_invites || [])]);
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
      setLocalSharedWith([]);
      setFileList([]);
    }
  }, [pet, isEditing, reset]);
  // The typed fields come back after a session that ran out (the photo and the sharing do not).
  useSessionDraft({ dirty: isDirty, getValues, reset, ready: !isEditing || !!pet, release });

  const dateColumns = useMemo(() => {
    let month = new Date().getMonth();
    let year = new Date().getFullYear();

    if (internalPickerDate.length === 3) {
      month = parseInt(internalPickerDate[1]);
      year = parseInt(internalPickerDate[2]);
    } else if (birthDateValue) {
      // "YYYY-MM-DD" parsed by new Date() is UTC midnight; the local
      // getters below would then report the previous day west of UTC.
      const d = parseRecordDate(birthDateValue);
      if (d) {
        month = d.getMonth();
        year = d.getFullYear();
      }
    }

    const daysCount = new Date(year, month + 1, 0).getDate();
    const days = Array.from({ length: daysCount }, (_, i) => ({
      label: String(i + 1).padStart(2, '0'),
      value: String(i + 1),
    }));
    const months = [
      'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
      'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
    ].map((m, i) => ({ label: m, value: String(i) }));
    const currentYear = new Date().getFullYear();
    const years = Array.from({ length: 51 }, (_, i) => {
      const y = currentYear - 50 + i;
      return { label: String(y), value: String(y) };
    });
    return [days, months, years];
  }, [internalPickerDate, birthDateValue]);

  // Looked up once typing pauses: only a whole login matches, so asking
  // after every letter would only flash «не найден» mid-word.
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [searchedTerm, setSearchedTerm] = useState('');
  const handleSearch = (val: string) => {
    setSearchTerm(val);
    if (searchTimer.current) clearTimeout(searchTimer.current);
    if (val.trim().length < 2) {
      setSearchResults([]);
      setSearchedTerm('');
      return;
    }
    searchTimer.current = setTimeout(async () => {
      setSearchLoading(true);
      try {
        const results = await usersService.searchUsers(val.trim());
        const currentUsername = localStorage.getItem('username');
        setSearchResults(results.filter(u => u.username !== currentUsername && !localSharedWith.includes(u.username)));
        setSearchedTerm(val);
      } catch (error) {
        console.error('Search error:', error);
      } finally {
        setSearchLoading(false);
      }
    }, 500);
  };

  const handleAddSharedUser = (username: string) => {
    if (!localSharedWith.includes(username)) {
      setLocalSharedWith(prev => [...prev, username]);
      setSearchTerm('');
      setSearchResults([]);
    }
  };

  const handleRemoveSharedUser = async (username: string) => {
    // Taking access from someone who has it is not undone by a tap on the bin: ask. A pending invitation is only withdrawn.
    if ((pet?.shared_with || []).includes(username)) {
      const confirmed = await Dialog.confirm({
        title: 'Закрыть доступ',
        content: `${username} больше не увидит «${pet?.name ?? 'питомца'}» и его записи. Доступ закроется после «Сохранить»`,
        confirmText: 'Закрыть доступ',
        cancelText: 'Оставить',
      });
      if (!confirmed) return;
    }
    setLocalSharedWith(prev => prev.filter(u => u !== username));
  };

  const onSubmit = async (values: PetFormData) => {
    let invited = false;
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
        const newPet = await petsService.createPet({ ...petData, tiles_settings: defaultTilesFor(values.species) });
        petId = newPet._id;
        createdPet = newPet;
      }

      if (petId) {
        const initialShared = [...(pet?.shared_with || []), ...(pet?.share_invites || [])];
        const toAdd = localSharedWith.filter(u => !initialShared.includes(u));
        const toRemove = initialShared.filter(u => !localSharedWith.includes(u));

        await Promise.all([
          ...toAdd.map(username => petsService.sharePet(petId!, username)),
          ...toRemove.map(username => petsService.unsharePet(petId!, username))
        ]);

        // Opened to the wrong person: take it back right away.
        if (toAdd.length > 0) {
          invited = true;
          const sharedPetId = petId;
          showUndo({
            message: `Приглашение отправлено: ${toAdd.join(', ')}`,
            onUndo: async () => {
              await Promise.all(toAdd.map(username => petsService.unsharePet(sharedPetId, username)));
              await queryClient.invalidateQueries({ queryKey: ['pets'] });
              await queryClient.invalidateQueries({ queryKey: ['pet', sharedPetId] });
            },
          });
        }
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
      // An invitation has its own message with «Отменить»: a second one would take its place at once.
      if (!invited) showToast.success('Питомец обновлён');
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
  // An address of a pet that is not there, or not the person's: said so, not an empty form to fill in.
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
          marginBottom: 'var(--spacing-lg)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          minHeight: '40px'
        }}>
          <h1 style={{ fontSize: 'var(--text-xxl)', fontWeight: 600, margin: 0 }}>
            {isEditing ? 'Редактировать питомца' : 'Добавить питомца'}
          </h1>
        </div>

        {readOnly && (
          <p className="safe-area-padding" role="note" style={{ margin: '0 0 var(--spacing-md)', color: 'var(--app-text-secondary)' }}>
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
                  if (file) {
                    setCropTarget({ src: URL.createObjectURL(file), filename: file.name });
                  }
                  e.target.value = '';
                }}
              />

              {fileList.length > 0 && fileList[0]?.url ? (
                // Photo exists - show photo card with overlay actions
                <div
                  style={{
                    position: 'relative',
                    width: '120px',
                    height: '120px',
                    borderRadius: '16px',
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
                        fontSize: '16px',
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
                        fontSize: '16px',
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
                    fontSize: '12px',
                    color: 'var(--adm-color-text-secondary)',
                    textAlign: 'center'
                  }}>
                    Добавить
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
              render={({ field: { value, onChange } }) => {
                let pickerValue: string[] = [];
                if (value) {
                  const d = parseRecordDate(value);
                  if (d) {
                    pickerValue = [String(d.getDate()), String(d.getMonth()), String(d.getFullYear())];
                  }
                } else {
                  const now = new Date();
                  pickerValue = [String(now.getDate()), String(now.getMonth()), String(now.getFullYear())];
                }

                const displayDate = value
                  ? (parseRecordDate(value)?.toLocaleDateString('ru-RU') ?? value)
                  : '';
                return (
                  <Form.Item
                    label="Дата рождения"
                    clickable
                    onClick={() => {
                      setInternalPickerDate(pickerValue);
                      setDatePickerVisible(true);
                    }}
                    arrow
                  >
                    <PickerValue id="birth_date" value={displayDate} placeholder="Выберите дату" />
                    <Picker
                      columns={dateColumns}
                      visible={datePickerVisible}
                      onClose={() => setDatePickerVisible(false)}
                      value={internalPickerDate.length ? internalPickerDate : pickerValue}
                      onSelect={(val) => setInternalPickerDate(val as string[])}
                      onConfirm={(val) => {
                        const day = val[0];
                        const month = parseInt(val[1] as string);
                        const year = val[2];
                        const monthStr = String(month + 1).padStart(2, '0');
                        const dayStr = String(day).padStart(2, '0');
                        const picked = `${year}-${monthStr}-${dayStr}`;
                        // The wheel offers the months still to come this year; a pet is not born in the future.
                        const today = new Date();
                        const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
                        if (picked > todayStr) {
                          showToast.info('Дата рождения не может быть позже сегодняшней');
                          onChange(todayStr);
                        } else {
                          onChange(picked);
                        }
                        setDatePickerVisible(false);
                        setInternalPickerDate([]);
                      }}
                      cancelText="Отмена"
                      confirmText="Готово"
                    />
                  </Form.Item>
                );
              }}
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
                      {selectedLabel || 'Не выбран'}
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

          {/* Sharing is an owner-only capability — the backend already
              rejects a non-owner's attempt to add/remove access, but the
              legacy app also kept the whole section out of a shared
              user's view (and never showed it while creating a new pet,
              since ownership only exists once the pet does). Showing it
              unconditionally here let a shared user see who else has
              access and try owner-only actions the old app deliberately
              hid from them. */}
          {isEditing && pet?.current_user_is_owner && (
          <Form layout="horizontal" mode="card">
            <Form.Header>Поделиться доступом</Form.Header>
            <p style={{
              margin: '0 var(--spacing-md) var(--spacing-sm)',
              fontSize: 'var(--text-sm)',
              color: 'var(--app-text-secondary)',
            }}>
              Человек получит приглашение и увидит питомца, когда примет его. Тогда он сможет смотреть и добавлять записи и данные для врача. Менять карточку питомца, плитки и доступ сможете только вы. Подсказываем тех, с кем вы уже делитесь питомцами; остальных найдём по полному логину
            </p>
            <Form.Item layout="vertical">
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <SearchBar
                  placeholder="Логин пользователя"
                  value={searchTerm}
                  onChange={handleSearch}
                  onClear={() => {
                    setSearchTerm('');
                    setSearchResults([]);
                  }}
                />
                {searchLoading && <div style={{ padding: '8px', textAlign: 'center' }}>Поиск...</div>}
                {/* Only an exact login matches (web/users.py), so say when none does. */}
                {!searchLoading && searchedTerm === searchTerm && searchTerm.trim().length >= 2 && searchResults.length === 0 && (
                  <div style={{ padding: '4px 8px', fontSize: 'var(--text-sm)', color: 'var(--app-text-secondary)' }}>
                    Пользователь с таким логином не найден
                  </div>
                )}
                {!searchLoading && searchResults.length > 0 && (
                  <div style={{
                    marginTop: '4px',
                    border: '1px solid var(--app-border-color)',
                    borderRadius: '8px',
                    maxHeight: '200px',
                    overflowY: 'auto',
                    backgroundColor: 'var(--app-page-background)'
                  }}>
                    {searchResults.map(u => (
                      <button
                        type="button"
                        key={u.username}
                        onClick={() => handleAddSharedUser(u.username)}
                        style={{
                          padding: '12px',
                          border: 'none',
                          borderBottom: '1px solid var(--app-border-color)',
                          background: 'transparent',
                          textAlign: 'left',
                          width: '100%',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          color: 'inherit',
                          font: 'inherit',
                        }}
                      >
                        <span style={{ fontWeight: 500 }}>{u.username}</span>
                        <UserAddOutline color='var(--adm-color-primary)' fontSize={20} />
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </Form.Item>

            {localSharedWith.length > 0 && localSharedWith.map(username => (
              <Form.Item
                key={username}
                extra={
                  <Button
                    size="mini"
                    color="danger"
                    fill="none"
                    onClick={() => handleRemoveSharedUser(username)}
                    aria-label={(pet?.shared_with || []).includes(username) ? `Закрыть доступ для ${username}` : `Отменить приглашение для ${username}`}
                  >
                    <DeleteOutline fontSize={20} aria-hidden />
                  </Button>
                }
              >
                {(pet?.shared_with || []).includes(username) ? (
                  <>
                  <button
                    type="button"
                    onClick={() => navigate(`/users/${username}`)}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '8px',
                      background: 'none',
                      border: 'none',
                      padding: 0,
                      cursor: 'pointer',
                      font: 'inherit',
                      color: 'inherit',
                    }}
                  >
                    <UserAvatar username={username} size={24} />
                    <span style={{ fontWeight: 500 }}>{username}</span>
                  </button>
                  {username === pet?.next_owner && (
                    // The family is an order: if the owner's account goes, the pet goes to the first of them.
                    <span style={{ display: 'block', marginTop: 4, fontSize: 'var(--text-xs)', color: 'var(--app-text-secondary)' }}>
                      Станет владельцем, если вы удалите аккаунт
                    </span>
                  )}
                  </>
                ) : (
                  // Invited, not a member yet: no profile to open.
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                    <UserAvatar username={username} size={24} />
                    <span style={{ fontWeight: 500 }}>{username}</span>
                    <span style={{ fontSize: 'var(--text-sm)', color: 'var(--app-text-secondary)' }}>
                      {(pet?.share_invites || []).includes(username) ? 'ждёт ответа' : 'приглашение уйдёт при сохранении'}
                    </span>
                  </span>
                )}
              </Form.Item>
            ))}
          </Form>
          )}

          {isEditing && id && pet && (
            // One place for the pet's events: its own screen. This row takes the person there for this pet.
            <Form layout="horizontal" mode="card">
              <Form.Item
                label="События питомца"
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



          <div className="safe-area-padding" style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--spacing-md)',
            marginTop: 'var(--spacing-xl)',
            paddingBottom: 'var(--spacing-xl)',
          }}>
            {!readOnly && (
              <>
                <button
                  style={{ display: 'none' }}
                  type="submit"
                  onClick={(e) => { e.preventDefault(); handleSubmit(onSubmit, onInvalidSubmit)(); }}
                />
                <SpinnerButton
                  loading={loading}
                  onClick={() => handleSubmit(onSubmit, onInvalidSubmit)()}
                  style={{ borderRadius: 'var(--radius-md)', fontWeight: 600 }}
                >
                  {isEditing ? 'Сохранить' : 'Добавить'}
                </SpinnerButton>
              </>
            )}
            <Button
              block
              size="large"
              onClick={() => goBack(navigate, '/pets')}
              style={{ borderRadius: 'var(--radius-md)', fontWeight: 500 }}
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
                  goBack(navigate, '/pets');
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
                  goBack(navigate, '/pets');
                }}
              />
            )}
          </div>
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
