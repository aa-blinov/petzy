import { useEffect, useMemo, useState, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Button, Form, Input, Picker, List, Switch, TextArea, SearchBar, ImageViewer } from 'antd-mobile';
import { UserAddOutline, DeleteOutline } from 'antd-mobile-icons';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors } from '@dnd-kit/core';
import type { DragEndEvent } from '@dnd-kit/core';
import { arrayMove, SortableContext, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';

import { petsService } from '../services/pets.service';
import { usersService } from '../services/users.service';
import { usePetTilesSettings } from '../hooks/usePetTilesSettings';
import { tilesConfig } from '../utils/tilesConfig';
import { LoadingSpinner } from '../components/LoadingSpinner';

const petSchema = z.object({
  name: z.string().min(1, 'Имя питомца обязательно'),
  breed: z.string().optional(),
  species: z.string().optional(),
  birth_date: z.string().optional(),
  gender: z.string().optional(),
  is_neutered: z.boolean().optional(),
  health_notes: z.string().optional(),
});

type PetFormData = z.infer<typeof petSchema>;

export function PetForm() {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const isEditing = !!id;
  const queryClient = useQueryClient();

  const [fileList, setFileList] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [datePickerVisible, setDatePickerVisible] = useState(false);
  const [neuteredPickerVisible, setNeuteredPickerVisible] = useState(false);
  const [internalPickerDate, setInternalPickerDate] = useState<string[]>([]);

  // State for Image Viewer to avoid imperative ImageViewer.show()
  const [imageViewer, setImageViewer] = useState<{ visible: boolean; image: string | null }>({
    visible: false,
    image: null,
  });

  // Track if form was initialized for this pet to prevent overwriting user changes
  const initializedPetId = useRef<string | null>(null);

  // Refs for focusing inputs on row click
  const nameInputRef = useRef<any>(null);
  const speciesInputRef = useRef<any>(null);
  const breedInputRef = useRef<any>(null);
  const genderInputRef = useRef<any>(null);
  const healthNotesInputRef = useRef<any>(null);

  const { control, handleSubmit, reset, watch } = useForm<PetFormData>({
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
      const d = new Date(birthDateValue);
      if (!isNaN(d.getTime())) {
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

  const neuteredOptions = [
    { label: 'Да', value: 'true' },
    { label: 'Нет', value: 'false' },
  ];

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

      // Use alert instead of Toast to avoid React 19 compatibility issues
      alert(isEditing ? 'Питомец обновлен' : 'Питомец добавлен');
      navigate('/pets');
    } catch (error: any) {
      const errorMessage = error?.response?.data?.error || 'Ошибка при сохранении';
      // Use alert instead of Toast to avoid React 19 compatibility issues with imperative APIs
      alert(errorMessage);
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
          <h2 style={{ fontSize: 'var(--text-xxl)', fontWeight: 600, margin: 0 }}>
            {isEditing ? 'Редактировать питомца' : 'Добавить питомца'}
          </h2>
        </div>

        <div>
          <Form
            layout="horizontal"
            mode="card"
          >
            <Form.Header>Общие настройки</Form.Header>
            <Controller
              name="name"
              control={control}
              render={({ field, fieldState: { error } }) => (
                <Form.Item
                  label="Имя"
                  required
                  help={error?.message}
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
              render={({ field }) => (
                <Form.Item
                  label="Вид питомца"
                  clickable
                  onClick={() => speciesInputRef.current?.focus()}
                >
                  <Input
                    {...field}
                    ref={speciesInputRef}
                    id="species"
                    placeholder="Кот, Собака..."
                  />
                </Form.Item>
              )}
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
                  const d = new Date(value);
                  if (!isNaN(d.getTime())) {
                    pickerValue = [String(d.getDate()), String(d.getMonth()), String(d.getFullYear())];
                  }
                } else {
                  const now = new Date();
                  pickerValue = [String(now.getDate()), String(now.getMonth()), String(now.getFullYear())];
                }

                const displayDate = value ? new Date(value).toLocaleDateString('ru-RU') : '';
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
              render={({ field }) => (
                <Form.Item
                  label="Пол"
                  clickable
                  onClick={() => genderInputRef.current?.focus()}
                >
                  <Input
                    {...field}
                    ref={genderInputRef}
                    id="gender"
                    placeholder="Необязательно"
                  />
                </Form.Item>
              )}
            />

            <Controller
              name="is_neutered"
              control={control}
              render={({ field: { value, onChange } }) => (
                <Form.Item
                  label="Стерилизация"
                  clickable
                  onClick={() => setNeuteredPickerVisible(true)}
                  arrow
                >
                  <Input
                    readOnly
                    value={value ? 'Да' : 'Нет'}
                  />
                  <Picker
                    columns={[neuteredOptions]}
                    visible={neuteredPickerVisible}
                    onClose={() => setNeuteredPickerVisible(false)}
                    value={[String(value)]}
                    onConfirm={(val) => {
                      onChange(val[0] === 'true');
                      setNeuteredPickerVisible(false);
                    }}
                    cancelText="Отмена"
                    confirmText="Сохранить"
                  />
                </Form.Item>
              )}
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
                style={{ display: 'none' }}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) {
                    setFileList([{
                      url: URL.createObjectURL(file),
                      file: file
                    }]);
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
                      📷
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
                      title="Удалить фото"
                    >
                      ×
                    </button>
                  </div>
                </div>
              ) : (
                // No photo - show upload zone
                <div
                  onClick={() => document.getElementById('pet-photo-input')?.click()}
                  style={{
                    width: '120px',
                    height: '120px',
                    borderRadius: '16px',
                    border: '2px dashed var(--adm-color-border)',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                    cursor: 'pointer',
                    background: 'var(--adm-color-fill-light)',
                    transition: 'all 0.2s ease',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = 'var(--adm-color-primary)';
                    e.currentTarget.style.background = 'var(--adm-color-fill-secondary)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = 'var(--adm-color-border)';
                    e.currentTarget.style.background = 'var(--adm-color-fill-light)';
                  }}
                >
                  <span style={{ fontSize: '32px', opacity: 0.6 }}>📷</span>
                  <span style={{
                    fontSize: '12px',
                    color: 'var(--adm-color-text-secondary)',
                    textAlign: 'center'
                  }}>
                    Добавить
                  </span>
                </div>
              )}
            </Form.Item>
          </Form>

          <Form layout="horizontal" mode="card">
            <Form.Header>Поделиться доступом</Form.Header>
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
                      <div
                        key={u.username}
                        onClick={() => handleAddSharedUser(u.username)}
                        style={{
                          padding: '12px',
                          borderBottom: '1px solid var(--app-border-color)',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between'
                        }}
                      >
                        <span style={{ fontWeight: 500 }}>{u.username}</span>
                        <UserAddOutline color='var(--adm-color-primary)' fontSize={20} />
                      </div>
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
                  >
                    <DeleteOutline fontSize={20} />
                  </Button>
                }
              >
                <span style={{ fontWeight: 500 }}>{username}</span>
              </Form.Item>
            ))}
          </Form>

          {isEditing && id && (
            <Form layout="horizontal" mode="card">
              <Form.Header>Настройка разделов дневника</Form.Header>
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
              onClick={(e) => { e.preventDefault(); handleSubmit(onSubmit)(); }}
            />
            <Button
              block
              color="primary"
              size="large"
              onClick={() => handleSubmit(onSubmit)()}
              loading={loading}
              style={{ borderRadius: 'var(--radius-md)', fontWeight: 600 }}
            >
              {isEditing ? 'Сохранить' : 'Добавить'}
            </Button>
            <Button
              block
              size="large"
              onClick={() => navigate('/pets')}
              style={{ borderRadius: 'var(--radius-md)', fontWeight: 500 }}
            >
              Отмена
            </Button>
          </div>
        </div>
      </div>
      <ImageViewer
        image={imageViewer.image || ''}
        visible={imageViewer.visible}
        onClose={() => setImageViewer(prev => ({ ...prev, visible: false }))}
        afterClose={() => setImageViewer({ visible: false, image: null })}
      />
    </div>
  );
}

function PetTilesSettingsSection({ petId }: { petId: string }) {
  const { tilesSettings, updateOrder, toggleVisibility } = usePetTilesSettings(petId);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      const oldIndex = tilesSettings.order.indexOf(active.id as string);
      const newIndex = tilesSettings.order.indexOf(over.id as string);
      updateOrder(arrayMove(tilesSettings.order, oldIndex, newIndex));
    }
  };

  function SortableTileItem({ id, title, visible, onToggle }: { id: string; title: string; visible: boolean; onToggle: (id: string, visible: boolean) => void }) {
    const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
    const style = {
      transform: CSS.Transform.toString(transform),
      transition,
      opacity: isDragging ? 0.5 : 1,
      zIndex: isDragging ? 1000 : 'auto',
      position: 'relative' as const,
    };

    return (
      <div ref={setNodeRef} style={style}>
        <List.Item
          prefix={
            <div {...attributes} {...listeners} style={{ cursor: 'grab', color: 'var(--app-text-tertiary)', fontSize: '20px', paddingRight: '8px', touchAction: 'none' }}>
              ☰
            </div>
          }
          extra={<Switch checked={visible} onChange={(checked) => onToggle(id, checked)} aria-label={`Показать ${title}`} />}
        >
          {title}
        </List.Item>
      </div>
    );
  }

  return (
    <>
      <Form.Item layout="vertical">
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={tilesSettings.order} strategy={verticalListSortingStrategy}>
            <List style={{ '--background-color': 'transparent' } as any}>
              {tilesSettings.order.map((tileId) => {
                const tile = tilesConfig.find((t) => t.id === tileId);
                if (!tile || tile.isTile === false) return null;
                return (
                  <SortableTileItem
                    key={tile.id}
                    id={tile.id}
                    title={tile.title}
                    visible={tilesSettings.visible[tile.id] !== false}
                    onToggle={toggleVisibility}
                  />
                );
              })}
            </List>
          </SortableContext>
        </DndContext>
        <div style={{
          marginTop: 'var(--spacing-sm)',
          fontSize: 'var(--text-xs)',
          color: 'var(--app-text-tertiary)',
          lineHeight: 'var(--line-height-tight)'
        }}>
          Перетащите тайлы для изменения порядка. Снимите галочку, чтобы скрыть тайл.
        </div>
      </Form.Item>
    </>
  );
}
