import { useState, useEffect, useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Button, Form, Input, ImageUploader, Toast, Picker } from 'antd-mobile';
import { RightOutline } from 'antd-mobile-icons';
import { petsService } from '../services/pets.service';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { usePetTilesSettings } from '../hooks/usePetTilesSettings';
import { tilesConfig } from '../utils/tilesConfig';
import { DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors } from '@dnd-kit/core';
import type { DragEndEvent } from '@dnd-kit/core';
import { arrayMove, SortableContext, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { List, Switch } from 'antd-mobile';

export function PetForm() {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const isEditing = !!id;
  const [form] = Form.useForm();
  const [fileList, setFileList] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [datePickerVisible, setDatePickerVisible] = useState(false);
  const [internalPickerDate, setInternalPickerDate] = useState<string[]>([]);
  const queryClient = useQueryClient();
  
  const birthDateValue = Form.useWatch('birth_date', form);

  // Fetch pet data if editing
  const { data: pet, isLoading: isLoadingPet } = useQuery({
    queryKey: ['pets', id],
    queryFn: async () => {
      if (!id) return null;
      const pets = await petsService.getPets();
      return pets.find(p => p._id === id) || null;
    },
    enabled: isEditing && !!id,
  });

  // Generate date columns dynamically [Day, Month, Year]
  const dateColumns = useMemo(() => {
    // Determine which month and year to use for day calculation
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

    // Get days in current selected month/year
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
    const years = Array.from({ length: 21 }, (_, i) => {
      const y = currentYear - 10 + i;
      return { label: String(y), value: String(y) };
    });

    return [days, months, years];
  }, [internalPickerDate, birthDateValue]);

  // Load pet data into form when editing
  useEffect(() => {
    if (pet) {
      form.setFieldsValue({
        name: pet.name,
        breed: pet.breed || '',
        birth_date: pet.birth_date || '',
        gender: pet.gender || '',
        species: pet.species || '',
      });
      if (pet.photo_url) {
        setFileList([{ url: pet.photo_url }]);
      } else {
        setFileList([]);
      }
    } else if (!isEditing) {
      // Reset form for new pet
      form.resetFields();
      setFileList([]);
    }
  }, [pet, isEditing, form]);

  const handleSubmit = async () => {
    try {
      await form.validateFields();
      const values = form.getFieldsValue();
      setLoading(true);

      // birth_date is already in YYYY-MM-DD format from Picker
      const birthDate = values.birth_date || '';

      const petData = {
        ...values,
        birth_date: birthDate,
        photo_file: fileList[0]?.file,
        photo_url: fileList[0]?.url,
        remove_photo: fileList.length === 0 && pet?.photo_url ? true : undefined,
      };

      if (isEditing && id) {
        await petsService.updatePet(id, petData);
        Toast.show({ icon: 'success', content: 'Питомец обновлен' });
      } else {
        await petsService.createPet(petData);
        Toast.show({ icon: 'success', content: 'Питомец добавлен' });
      }

      await queryClient.invalidateQueries({ queryKey: ['pets'] });
      
      // Navigate back after success
      setTimeout(() => {
        navigate('/pets');
      }, 500);
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
    return (
      <div style={{ 
        minHeight: '100vh', 
        paddingTop: 'calc(env(safe-area-inset-top) + 88px)',
        paddingBottom: 'calc(env(safe-area-inset-bottom) + 80px)',
        backgroundColor: 'var(--app-page-background)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'var(--app-text-color)'
      }}>
        Загрузка...
      </div>
    );
  }

  return (
    <div style={{ 
      minHeight: '100vh', 
      paddingTop: 'calc(env(safe-area-inset-top) + 88px)',
      paddingBottom: 'calc(env(safe-area-inset-bottom) + 80px)',
      backgroundColor: 'var(--app-page-background)',
      color: 'var(--app-text-color)'
    }}>
      <div style={{ maxWidth: '800px', margin: '0 auto' }}>
        <div style={{ 
          marginBottom: '16px', 
          paddingLeft: 'max(16px, env(safe-area-inset-left))', 
          paddingRight: 'max(16px, env(safe-area-inset-right))' 
        }}>
          <h2 style={{ color: 'var(--app-text-color)', fontSize: '24px', fontWeight: 600, margin: 0 }}>
            {isEditing ? 'Редактировать питомца' : 'Добавить питомца'}
          </h2>
        </div>

        <div style={{ 
          paddingLeft: 'max(16px, env(safe-area-inset-left))',
          paddingRight: 'max(16px, env(safe-area-inset-right))'
        }}>
          <Form
            form={form}
            layout="vertical"
            footer={
              <div style={{ display: 'flex', gap: '8px', marginTop: '16px' }}>
                <Button
                  onClick={() => navigate('/pets')}
                  style={{ flex: 1 }}
                >
                  Отмена
                </Button>
                <Button
                  color="primary"
                  onClick={handleSubmit}
                  loading={loading}
                  style={{ flex: 1 }}
                >
                  {isEditing ? 'Сохранить' : 'Добавить'}
                </Button>
              </div>
            }
          >
            <Form.Item
              name="name"
              label="Имя"
              rules={[{ required: true, message: 'Введите имя питомца' }]}
            >
              <Input placeholder="Имя питомца" />
            </Form.Item>

            <Form.Item name="breed" label="Порода">
              <Input placeholder="Порода (необязательно)" />
            </Form.Item>

            <Form.Item name="birth_date" label="Дата рождения">
              {(() => {
                // Initial value for the picker drums
                let pickerValue: string[] = [];
                if (birthDateValue) {
                  const d = new Date(birthDateValue);
                  if (!isNaN(d.getTime())) {
                    pickerValue = [String(d.getDate()), String(d.getMonth()), String(d.getFullYear())];
                  }
                } else {
                  const now = new Date();
                  pickerValue = [String(now.getDate()), String(now.getMonth()), String(now.getFullYear())];
                }

                const displayDate = birthDateValue ? new Date(birthDateValue).toLocaleDateString('ru-RU') : 'Выберите дату';
                
                return (
                  <>
                    <div 
                      onClick={() => {
                        setInternalPickerDate(pickerValue);
                        setDatePickerVisible(true);
                      }}
                      style={{ 
                        padding: '8px 0',
                        cursor: 'pointer',
                        color: 'var(--adm-color-text)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        justifyContent: 'flex-start'
                      }}
                    >
                      <span>{displayDate}</span>
                      <RightOutline style={{ color: 'var(--adm-color-weak)', fontSize: '14px' }} />
                    </div>
                    <Picker
                      columns={dateColumns}
                      visible={datePickerVisible}
                      onClose={() => setDatePickerVisible(false)}
                      value={internalPickerDate.length ? internalPickerDate : pickerValue}
                      onSelect={(val) => {
                        setInternalPickerDate(val as string[]);
                      }}
                      onConfirm={(val) => {
                        const day = val[0];
                        const month = parseInt(val[1] as string);
                        const year = val[2];
                        
                        const monthStr = String(month + 1).padStart(2, '0');
                        const dayStr = String(day).padStart(2, '0');
                        const formattedDate = `${year}-${monthStr}-${dayStr}`;
                        
                        form.setFieldValue('birth_date', formattedDate);
                        setDatePickerVisible(false);
                        setInternalPickerDate([]); // Clear temp state
                      }}
                      cancelText="Отмена"
                      confirmText="Сохранить"
                    />
                  </>
                );
              })()}
            </Form.Item>
            
            <Form.Item name="gender" label="Пол">
              <Input placeholder="Пол (необязательно)" />
            </Form.Item>

            <Form.Item name="photo" label="Фото">
              <ImageUploader
                value={fileList}
                onChange={setFileList}
                upload={async (file) => {
                  return {
                    url: URL.createObjectURL(file),
                  };
                }}
                maxCount={1}
                deletable={true}
              />
            </Form.Item>

            {isEditing && id && (
              <PetTilesSettingsSection petId={id} />
            )}
          </Form>
        </div>
      </div>
    </div>
  );
}

// Component for tiles settings in pet form
function PetTilesSettingsSection({ petId }: { petId: string }) {
  const { tilesSettings, updateOrder, toggleVisibility } = usePetTilesSettings(petId);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;

    if (over && active.id !== over.id) {
      const oldIndex = tilesSettings.order.indexOf(active.id as string);
      const newIndex = tilesSettings.order.indexOf(over.id as string);
      const newOrder = arrayMove(tilesSettings.order, oldIndex, newIndex);
      updateOrder(newOrder);
    }
  };

  function SortableTileItem({ id, title, visible, onToggle }: { id: string; title: string; visible: boolean; onToggle: (id: string, visible: boolean) => void }) {
    const {
      attributes,
      listeners,
      setNodeRef,
      transform,
      transition,
      isDragging,
    } = useSortable({ id });

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
            <div
              {...attributes}
              {...listeners}
              style={{ cursor: 'grab', color: '#999', fontSize: '20px', paddingRight: '8px', touchAction: 'none' }}
            >
              ☰
            </div>
          }
          extra={
            <Switch
              checked={visible}
              onChange={(checked) => onToggle(id, checked)}
            />
          }
        >
          {title}
        </List.Item>
      </div>
    );
  }

  return (
    <Form.Item label="Настройки тайлов дневника">
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext
          items={tilesSettings.order}
          strategy={verticalListSortingStrategy}
        >
          <List>
            {tilesSettings.order.map((tileId) => {
              const tile = tilesConfig.find((t) => t.id === tileId);
              if (!tile) return null;

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
      <p style={{ marginTop: '8px', fontSize: '12px', color: 'var(--adm-color-weak)' }}>
        Перетащите тайлы для изменения порядка. Снимите галочку, чтобы скрыть тайл.
      </p>
    </Form.Item>
  );
}

