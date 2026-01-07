import { useEffect, useMemo, useState, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Button, Form, Input, ImageUploader, Toast, Picker, List, Switch, TextArea, SearchBar } from 'antd-mobile';
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
    if (pet) {
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
      const petData = {
        ...values,
        photo_file: fileList[0]?.file,
        photo_url: fileList[0]?.url,
        remove_photo: fileList.length === 0 && pet?.photo_url ? true : undefined,
      };

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

      Toast.show({ icon: 'success', content: isEditing ? 'Питомец обновлен' : 'Питомец добавлен' });
      await queryClient.invalidateQueries({ queryKey: ['pets'] });
      setTimeout(() => navigate('/pets'), 500);
    } catch (error: any) {
      Toast.show({
        icon: 'fail',
        content: error?.response?.data?.error || 'Ошибка при сохранении',
      });
    } finally {
      setLoading(false);
    }
  };

  if (isEditing && isLoadingPet) {
    return <LoadingSpinner />;
  }

  return (
    <div style={{
      minHeight: '100vh', paddingTop: 'calc(env(safe-area-inset-top) + 88px)',
      paddingBottom: 'calc(env(safe-area-inset-bottom) + 80px)',
      backgroundColor: 'var(--app-page-background)', color: 'var(--app-text-color)'
    }}>
      <div style={{ maxWidth: '800px', margin: '0 auto' }}>
        <div style={{ marginBottom: '16px', padding: '0 max(16px, env(safe-area-inset-left))' }}>
          <h2 style={{ fontSize: '24px', fontWeight: 600, margin: 0 }}>
            {isEditing ? 'Редактировать питомца' : 'Добавить питомца'}
          </h2>
        </div>

        <div style={{ padding: '0 max(16px, env(safe-area-inset-left))' }}>
          <Form
            layout="horizontal"
            mode="card"
          >
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
                    style={{ '--text-align': 'right' }}
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
                    style={{ '--text-align': 'right' }}
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
                    style={{ '--text-align': 'right' }}
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
                      style={{ '--text-align': 'right' }}
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
                    style={{ '--text-align': 'right' }}
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
                    style={{ '--text-align': 'right' }}
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
              <ImageUploader
                value={fileList}
                onChange={setFileList}
                upload={async (file) => ({ url: URL.createObjectURL(file) })}
                maxCount={1}
                deletable={true}
              />
            </Form.Item>

            {isEditing && id && <PetTilesSettingsSection petId={id} />}
          </Form>

          {isEditing && (
            <div style={{ marginTop: '24px' }}>
              <div style={{
                fontSize: 'var(--adm-font-size-main)',
                color: 'var(--adm-color-weak)',
                padding: '0 12px 8px'
              }}>
                Поделиться доступом
              </div>
              <List style={{
                '--background-color': 'var(--app-card-background)',
                borderRadius: '12px',
                overflow: 'hidden',
                boxShadow: '0 2px 8px rgba(0, 0, 0, 0.05)',
              } as React.CSSProperties}>
                <List.Item>
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
                        border: '1px solid var(--app-border-color)',
                        borderRadius: '8px',
                        maxHeight: '150px',
                        overflowY: 'auto'
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
                            <span>{u.username}</span>
                            <UserAddOutline color='var(--adm-color-primary)' />
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </List.Item>
                {localSharedWith.length > 0 && (
                  localSharedWith.map(username => (
                    <List.Item
                      key={username}
                      extra={
                        <Button
                          size="mini"
                          color="danger"
                          fill="none"
                          onClick={() => handleRemoveSharedUser(username)}
                        >
                          <DeleteOutline />
                        </Button>
                      }
                    >
                      {username}
                    </List.Item>
                  ))
                )}
              </List>
            </div>
          )}

          <div style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
            marginTop: '24px',
            paddingBottom: '24px'
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
              style={{ borderRadius: '12px', fontWeight: 600 }}
            >
              {isEditing ? 'Сохранить' : 'Добавить'}
            </Button>
            <Button
              block
              size="large"
              onClick={() => navigate('/pets')}
              style={{ borderRadius: '12px', fontWeight: 500 }}
            >
              Отмена
            </Button>
          </div>
        </div>
      </div>
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
            <div {...attributes} {...listeners} style={{ cursor: 'grab', color: '#999', fontSize: '20px', paddingRight: '8px', touchAction: 'none' }}>
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
    <div style={{ marginTop: '24px' }}>
      <div style={{
        fontSize: 'var(--adm-font-size-main)',
        color: 'var(--app-text-secondary)',
        padding: '0 12px 8px'
      }}>
        Настройки тайлов дневника
      </div>
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
      <p style={{ marginTop: '8px', fontSize: '12px', color: 'var(--adm-color-weak)', padding: '0 12px' }}>
        Перетащите тайлы для изменения порядка. Снимите галочку, чтобы скрыть тайл.
      </p>
    </div>
  );
}
