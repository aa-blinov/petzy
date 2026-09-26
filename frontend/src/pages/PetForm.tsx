import { useEffect, useMemo, useState, useRef } from 'react';
import { parseRecordDate } from '../utils/relativeTime';
import { showToast } from '../utils/toast';
import { getApiErrorMessage } from '../utils/apiError';
import { useNavigate, useParams } from 'react-router-dom';
import { goBack } from '../utils/navigation';
import { Button, Form, Input, Picker, TextArea, SearchBar, ImageViewer } from 'antd-mobile';
import type { InputRef, TextAreaRef } from 'antd-mobile';
import { UserAddOutline, DeleteOutline } from 'antd-mobile-icons';
import { Camera } from 'lucide-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

/** Predefined species — matches speciesIcon() in utils/speciesIcon.tsx
    so the lucide placeholder stays consistent. */
const SPECIES_OPTIONS = Object.entries(SPECIES_LABELS).map(([value, label]) => ({ label, value }));

/** Sterilisation (neutered) options. */
const NEUTERED_OPTIONS = [
    { label: 'Не указано', value: '' },
    { label: 'Нет', value: 'false' },
    { label: 'Да', value: 'true' },
];

import { petsService } from '../services/pets.service';
import { usersService } from '../services/users.service';
import { TilesEditor } from '../components/TilesEditor';
import { UserAvatar } from '../components/UserAvatar';
import { GENDER_OPTIONS, SPECIES_LABELS } from '../utils/constants';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { SpinnerButton } from '../components/SpinnerButton';
import { PhotoCropModal } from '../components/PhotoCropModal';
import { FieldError } from '../components/FieldError';
import { onInvalidSubmit } from '../utils/formErrors';
import { FormDangerButton } from '../components/FormDangerButton';
import { useDeletePet } from '../hooks/useDeletePet';

const petSchema = z.object({
  name: z.string().min(1, 'Введите имя питомца'),
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
  const deletePet = useDeletePet();
  const { id } = useParams<{ id: string }>();
  const isEditing = !!id;
  const queryClient = useQueryClient();

  const [fileList, setFileList] = useState<PetPhotoItem[]>([]);
  const [cropTarget, setCropTarget] = useState<{ src: string; filename: string } | null>(null);
  const [loading, setLoading] = useState(false);
  const [datePickerVisible, setDatePickerVisible] = useState(false);
  const [neuteredPickerVisible, setNeuteredPickerVisible] = useState(false);
  const [speciesPickerVisible, setSpeciesPickerVisible] = useState(false);
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

  const { control, handleSubmit, reset, watch } = useForm<PetFormData>({
    // onInvalidSubmit scrolls to and focuses the first error in page order;
    // RHF's own focus picked the first registered ref instead.
    shouldFocusError: false,
    resolver: zodResolver(petSchema),
    defaultValues: {
      name: '',
      breed: '',
      birth_date: '',
      gender: '',
      species: '',
      is_neutered: false,
      health_notes: '',
    }
  });

  const [searchTerm, setSearchTerm] = useState('');
  const [searchResults, setSearchResults] = useState<{ username: string }[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);

  const [localSharedWith, setLocalSharedWith] = useState<string[]>([]);

  const birthDateValue = watch('birth_date');

  const { data: pet, isLoading: isLoadingPet } = useQuery({
    queryKey: ['pets', id],
    queryFn: async () => {
      if (!id) return null;
      const pets = await petsService.getPets();
      return pets.find(p => p._id === id) || null;
    },
    enabled: isEditing && !!id,
  });

  useEffect(() => {
    if (pet && initializedPetId.current !== pet._id) {
      // Only initialize once per pet to prevent overwriting user changes
      initializedPetId.current = pet._id;
      reset({
        name: pet.name,
        breed: pet.breed || '',
        birth_date: pet.birth_date || '',
        gender: pet.gender || '',
        species: pet.species || '',
        is_neutered: pet.is_neutered || false,
        health_notes: pet.health_notes || '',
      });
      setLocalSharedWith(pet.shared_with || []);
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
        is_neutered: false,
        health_notes: '',
      });
      setLocalSharedWith([]);
      setFileList([]);
    }
  }, [pet, isEditing, reset]);

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

  const handleSearch = async (val: string) => {
    setSearchTerm(val);
    if (val.length < 2) {
      setSearchResults([]);
      return;
    }
    setSearchLoading(true);
    try {
      const results = await usersService.searchUsers(val);
      const currentUsername = localStorage.getItem('username');
      const filtered = results.filter(u => u.username !== currentUsername && !localSharedWith.includes(u.username));
      setSearchResults(filtered);
    } catch (error) {
      console.error('Search error:', error);
    } finally {
      setSearchLoading(false);
    }
  };

  const handleAddSharedUser = (username: string) => {
    if (!localSharedWith.includes(username)) {
      setLocalSharedWith(prev => [...prev, username]);
      setSearchTerm('');
      setSearchResults([]);
    }
  };

  const handleRemoveSharedUser = (username: string) => {
    setLocalSharedWith(prev => prev.filter(u => u !== username));
  };

  const onSubmit = async (values: PetFormData) => {
    try {
      setLoading(true);
      const hasNewFile = fileList[0]?.file instanceof File;
      const photoWasRemoved = fileList.length === 0 && !!pet?.photo_url;

      // Debug logging
      console.log('=== Photo Debug ===');
      console.log('fileList:', fileList);
      console.log('fileList.length:', fileList.length);
      console.log('pet?.photo_url:', pet?.photo_url);
      console.log('hasNewFile:', hasNewFile);
      console.log('photoWasRemoved:', photoWasRemoved);

      const petData = {
        ...values,
        photo_file: hasNewFile ? fileList[0].file : undefined,
        // Don't send photo_url for new files (blob URL) - only send when no change needed
        photo_url: undefined,
        remove_photo: photoWasRemoved ? true : undefined,
      };

      console.log('petData.remove_photo:', petData.remove_photo);

      let petId = id;
      if (isEditing && id) {
        await petsService.updatePet(id, petData);
      } else {
        const newPet = await petsService.createPet(petData);
        petId = newPet._id;
      }

      if (petId) {
        const initialShared = pet?.shared_with || [];
        const toAdd = localSharedWith.filter(u => !initialShared.includes(u));
        const toRemove = initialShared.filter(u => !localSharedWith.includes(u));

        await Promise.all([
          ...toAdd.map(username => petsService.sharePet(petId!, username)),
          ...toRemove.map(username => petsService.unsharePet(petId!, username))
        ]);
      }

      // Invalidate cache BEFORE navigating to ensure fresh data
      await queryClient.invalidateQueries({ queryKey: ['pets'] });
      if (petId) {
        await queryClient.invalidateQueries({ queryKey: ['pet', petId] });
      }

      showToast.success(isEditing ? 'Питомец обновлён' : 'Питомец добавлен', {
        afterClose: () => goBack(navigate, '/pets'),
      });
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

        <div>
          <Form
            layout="horizontal"
            mode="card"
            style={{
              '--prefix-width': '7em'
            } as React.CSSProperties}
          >
            <Form.Header>Общие настройки</Form.Header>
            <Controller
              name="name"
              control={control}
              render={({ field, fieldState: { error } }) => (
                <Form.Item
                  label="Имя"
                  required
                  description={error?.message ? <FieldError message={error.message} /> : undefined}
                  clickable
                  onClick={() => nameInputRef.current?.focus()}
                >
                  <Input
                    {...field}
                    ref={nameInputRef}
                    id="name"
                    placeholder="Имя питомца"
                  />
                </Form.Item>
              )}
            />

            <Controller
              name="species"
              control={control}
              render={({ field }) => {
                const selectedLabel = SPECIES_OPTIONS.find(o => o.value === field.value)?.label || '';
                return (
                  <Form.Item
                    label="Тип питомца"
                    clickable
                    arrow
                    onClick={() => setSpeciesPickerVisible(true)}
                  >
                    <span style={{ color: field.value ? 'var(--app-text-primary)' : 'var(--app-text-tertiary)' }}>
                      {selectedLabel || 'Не выбран'}
                    </span>
                    <Picker
                      columns={[SPECIES_OPTIONS]}
                      visible={speciesPickerVisible}
                      value={field.value ? [field.value] : []}
                      onClose={() => setSpeciesPickerVisible(false)}
                      onConfirm={(val) => {
                        field.onChange(val[0] as string);
                        setSpeciesPickerVisible(false);
                      }}
                      cancelText="Отмена"
                      confirmText="Выбрать"
                    />
                  </Form.Item>
                );
              }}
            />

            <Controller
              name="breed"
              control={control}
              render={({ field }) => (
                <Form.Item
                  label="Порода"
                  clickable
                  onClick={() => breedInputRef.current?.focus()}
                >
                  <Input
                    {...field}
                    ref={breedInputRef}
                    id="breed"
                    placeholder="Необязательно"
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
                    <Input
                      id="birth_date"
                      readOnly
                      value={displayDate}
                      placeholder="Выберите дату"
                    />
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
                        onChange(`${year}-${monthStr}-${dayStr}`);
                        setDatePickerVisible(false);
                        setInternalPickerDate([]);
                      }}
                      cancelText="Отмена"
                      confirmText="Сохранить"
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
                      confirmText="Выбрать"
                    />
                  </Form.Item>
                );
              }}
            />

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
                    label="Стерилизация"
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
                      confirmText="Выбрать"
                    />
                  </Form.Item>
                );
              }}
            />

            <Controller
              name="health_notes"
              control={control}
              render={({ field }) => (
                <Form.Item
                  label="Здоровье / Аллергии"
                  layout="vertical"
                >
                  <TextArea
                    {...field}
                    ref={healthNotesInputRef}
                    placeholder="Важная информация о здоровье"
                    autoSize={{ minRows: 2, maxRows: 5 }}
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
                    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
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
                      background: 'linear-gradient(transparent, rgba(0, 0, 0, 0.7))',
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
                        background: 'rgba(255, 255, 255, 0.9)',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '16px',
                      }}
                      title="Заменить фото"
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
                        background: 'rgba(255, 82, 82, 0.9)',
                        color: 'white',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '16px',
                        fontWeight: 'bold',
                      }}
                      aria-label="Удалить фото"
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
              Пользователь сможет добавлять и просматривать записи этого питомца так же, как вы
            </p>
            <Form.Item layout="vertical">
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <SearchBar
                  placeholder="Введите имя пользователя"
                  value={searchTerm}
                  onChange={handleSearch}
                  onClear={() => {
                    setSearchTerm('');
                    setSearchResults([]);
                  }}
                />
                {searchLoading && <div style={{ padding: '8px', textAlign: 'center' }}>Поиск...</div>}
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
                    aria-label={`Закрыть доступ для ${username}`}
                  >
                    <DeleteOutline fontSize={20} aria-hidden />
                  </Button>
                }
              >
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
              </Form.Item>
            ))}
          </Form>
          )}

          {isEditing && id && (
            <Form layout="horizontal" mode="card">
              <Form.Header>Плитки в ленте</Form.Header>
              <PetTilesSettingsSection petId={id} />
            </Form>
          )}



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
            <SpinnerButton
              loading={loading}
              onClick={() => handleSubmit(onSubmit, onInvalidSubmit)()}
              style={{ borderRadius: 'var(--radius-md)', fontWeight: 600 }}
            >
              {isEditing ? 'Сохранить' : 'Добавить'}
            </SpinnerButton>
            <Button
              block
              size="large"
              onClick={() => goBack(navigate, '/pets')}
              style={{ borderRadius: 'var(--radius-md)', fontWeight: 500 }}
            >
              Отмена
            </Button>
            {/* Only the owner can delete; the backend refuses anyone else. */}
            {isEditing && pet?.current_user_is_owner && (
              <FormDangerButton
                label="Удалить питомца"
                confirmTitle="Удаление питомца"
                confirmContent={`Удалить «${pet.name}»? Вместе с ним удалятся все записи, лекарства и документы`}
                onConfirm={async () => {
                  await deletePet(pet);
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
    </div>
  );
}

function PetTilesSettingsSection({ petId }: { petId: string }) {
  return (
    <Form.Item layout="vertical">
      <TilesEditor petId={petId} />
      <div style={{
        marginTop: 'var(--spacing-sm)',
        fontSize: 'var(--text-xs)',
        color: 'var(--app-text-tertiary)',
        lineHeight: 'var(--line-height-tight)'
      }}>
        Перетащите плитки, чтобы поменять порядок. Снимите галочку, чтобы скрыть плитку
      </div>
    </Form.Item>
  );
}
