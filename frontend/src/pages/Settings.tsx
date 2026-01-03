import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, List, Input, Selector, Switch, Form, Toast } from 'antd-mobile';
import { useTheme } from '../hooks/useTheme';
import { useTilesSettings } from '../hooks/useTilesSettings';
import { tilesConfig } from '../utils/tilesConfig';
import { DEFAULT_FORM_SETTINGS, getFormSettings, type FormSettings } from '../utils/formsConfig';
import { DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors } from '@dnd-kit/core';
import type { DragEndEvent } from '@dnd-kit/core';
import { arrayMove, SortableContext, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';

interface SortableTileItemProps {
  id: string;
  title: string;
  visible: boolean;
  onToggle: (id: string, visible: boolean) => void;
  disabled?: boolean;
}

function SortableTileItem({ id, title, visible, onToggle, disabled = false }: SortableTileItemProps) {
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
    <div
      ref={setNodeRef}
      style={style}
    >
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
            disabled={disabled}
          />
        }
      >
        {title}
      </List.Item>
    </div>
  );
}

export function Settings() {
  const navigate = useNavigate();
  const mountedRef = useRef(true);
  const { theme, setTheme } = useTheme();
  const { tilesSettings, updateOrder, toggleVisibility, resetSettings: resetTilesSettings } = useTilesSettings();
  const [formSettings, setFormSettings] = useState<FormSettings>(DEFAULT_FORM_SETTINGS);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

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

  useEffect(() => {
    const settings = getFormSettings();
    setFormSettings(settings);
  }, []);

  const handleDragEnd = useCallback((event: DragEndEvent) => {
    const { active, over } = event;

    if (over && active.id !== over.id) {
      const oldIndex = tilesSettings.order.indexOf(active.id as string);
      const newIndex = tilesSettings.order.indexOf(over.id as string);
      const newOrder = arrayMove(tilesSettings.order, oldIndex, newIndex);
      updateOrder(newOrder);
    }
  }, [tilesSettings.order, updateOrder]);

  const handleSave = useCallback(() => {
    try {
      localStorage.setItem('formDefaults', JSON.stringify(formSettings));
      Toast.show({
        icon: 'success',
        content: 'Настройки успешно сохранены',
        duration: 1000,
      });
      setTimeout(() => {
        if (mountedRef.current) {
          navigate('/');
        }
      }, 1000);
    } catch (err) {
      Toast.show({
        icon: 'fail',
        content: 'Ошибка при сохранении настроек',
      });
      console.error('Error saving settings:', err);
    }
  }, [formSettings, navigate]);

  const handleReset = useCallback(() => {
    const confirmed = window.confirm('Вы уверены, что хотите сбросить все настройки к значениям по умолчанию?');
    if (confirmed) {
      try {
        setFormSettings(DEFAULT_FORM_SETTINGS);
        localStorage.setItem('formDefaults', JSON.stringify(DEFAULT_FORM_SETTINGS));
        resetTilesSettings();
        Toast.show({
          icon: 'success',
          content: 'Настройки сброшены',
          duration: 1000,
        });
        setTimeout(() => {
          if (mountedRef.current) {
            navigate('/');
          }
        }, 1000);
      } catch (err) {
        Toast.show({
          icon: 'fail',
          content: 'Ошибка при сбросе настроек',
        });
      }
    }
  }, [resetTilesSettings, navigate]);

  const updateFormSetting = useCallback((formType: keyof FormSettings, field: string, value: string) => {
    setFormSettings(prev => ({
      ...prev,
      [formType]: {
        ...(prev[formType] || {}),
        [field]: value
      }
    }));
  }, []);

  return (
    <div style={{ 
      minHeight: '100vh', 
      backgroundColor: 'var(--app-page-background)',
      paddingTop: 'calc(env(safe-area-inset-top) + 88px)',
      paddingBottom: 'calc(env(safe-area-inset-bottom) + 80px)',
      color: 'var(--app-text-color)'
    }}>
      <div style={{ maxWidth: '800px', margin: '0 auto' }}>
        <div style={{ marginBottom: '16px', paddingLeft: 'max(16px, env(safe-area-inset-left))', paddingRight: 'max(16px, env(safe-area-inset-right))' }}>
          <h2 style={{ color: 'var(--app-text-color)', fontSize: '24px', fontWeight: 600, margin: 0 }}>Настройки</h2>
        </div>
        
        {/* Theme Section */}
        <List header="Внешний вид" mode="card">
          <List.Item
            extra={
              <Switch
                checked={theme === 'dark'}
                onChange={(checked) => setTheme(checked ? 'dark' : 'light')}
              />
            }
          >
            Темная тема
          </List.Item>
        </List>

        {/* Form Defaults Section */}
        <div style={{ marginBottom: '8px', paddingLeft: 'max(16px, env(safe-area-inset-left))', paddingRight: 'max(16px, env(safe-area-inset-right))' }}>
          <h3 style={{ margin: 0, fontSize: '14px', color: 'var(--app-text-secondary)', textTransform: 'uppercase' }}>Значения по умолчанию для форм</h3>
        </div>

        <Form layout="horizontal" mode="card">
          <Form.Header>Приступ астмы</Form.Header>
          <Form.Item label="Длительность">
            <Selector
              options={[
                { label: 'Короткий', value: 'Короткий' },
                { label: 'Средний', value: 'Средний' },
                { label: 'Длинный', value: 'Длинный' },
              ]}
              value={[formSettings.asthma?.duration || 'Короткий']}
              onChange={(arr) => updateFormSetting('asthma', 'duration', arr[0] || 'Короткий')}
              columns={2}
            />
          </Form.Item>
          <Form.Item label="Ингалятор">
            <Selector
              options={[
                { label: 'Нет', value: 'false' },
                { label: 'Да', value: 'true' },
              ]}
              value={[formSettings.asthma?.inhalation || 'false']}
              onChange={(arr) => updateFormSetting('asthma', 'inhalation', arr[0] || 'false')}
              columns={2}
            />
          </Form.Item>
          <Form.Item label="Причина">
            <Input
              value={formSettings.asthma?.reason || ''}
              onChange={(val) => updateFormSetting('asthma', 'reason', val)}
              placeholder="Введите причину"
            />
          </Form.Item>
        </Form>

        <Form layout="horizontal" mode="card">
          <Form.Header>Дефекация</Form.Header>
          <Form.Item label="Тип стула">
            <Selector
              options={[
                { label: 'Обычный', value: 'Обычный' },
                { label: 'Жидкий', value: 'Жидкий' },
                { label: 'Твердый', value: 'Твердый' },
              ]}
              value={[formSettings.defecation?.stool_type || 'Обычный']}
              onChange={(arr) => updateFormSetting('defecation', 'stool_type', arr[0] || 'Обычный')}
              columns={2}
            />
          </Form.Item>
          <Form.Item label="Цвет">
            <Input
              value={formSettings.defecation?.color || 'Коричневый'}
              onChange={(val) => updateFormSetting('defecation', 'color', val)}
              placeholder="Введите цвет"
            />
          </Form.Item>
          <Form.Item label="Корм">
            <Input
              value={formSettings.defecation?.food || ''}
              onChange={(val) => updateFormSetting('defecation', 'food', val)}
              placeholder="Введите корм"
            />
          </Form.Item>
        </Form>

        <Form layout="horizontal" mode="card">
          <Form.Header>Вес</Form.Header>
          <Form.Item label="Корм">
            <Input
              value={formSettings.weight?.food || ''}
              onChange={(val) => updateFormSetting('weight', 'food', val)}
              placeholder="Введите корм"
            />
          </Form.Item>
        </Form>

        <Form layout="horizontal" mode="card">
          <Form.Header>Закапывание глаз</Form.Header>
          <Form.Item label="Тип капель">
            <Selector
              options={[
                { label: 'Обычные', value: 'Обычные' },
                { label: 'Гелевые', value: 'Гелевые' },
              ]}
              value={[formSettings.eye_drops?.drops_type || 'Обычные']}
              onChange={(arr) => updateFormSetting('eye_drops', 'drops_type', arr[0] || 'Обычные')}
              columns={2}
            />
          </Form.Item>
        </Form>

        <Form layout="horizontal" mode="card">
          <Form.Header>Чистка зубов</Form.Header>
          <Form.Item label="Способ">
            <Selector
              options={[
                { label: 'Щетка', value: 'Щетка' },
                { label: 'Марля', value: 'Марля' },
                { label: 'Игрушка', value: 'Игрушка' },
              ]}
              value={[formSettings.tooth_brushing?.brushing_type || 'Щетка']}
              onChange={(arr) => updateFormSetting('tooth_brushing', 'brushing_type', arr[0] || 'Щетка')}
              columns={3}
            />
          </Form.Item>
        </Form>

        <Form layout="horizontal" mode="card">
          <Form.Header>Чистка ушей</Form.Header>
          <Form.Item label="Способ">
            <Selector
              options={[
                { label: 'Салфетка', value: 'Салфетка/Марля' },
                { label: 'Капли', value: 'Капли' },
              ]}
              value={[formSettings.ear_cleaning?.cleaning_type || 'Салфетка/Марля']}
              onChange={(arr) => updateFormSetting('ear_cleaning', 'cleaning_type', arr[0] || 'Салфетка/Марля')}
              columns={1}
            />
          </Form.Item>
        </Form>

        {/* Dashboard Tiles Section */}
        <List header="Настройка тайлов дашборда" mode="card">
          <div style={{ padding: '12px 16px', color: '#666', fontSize: '14px' }}>
            Перетащите тайлы для изменения порядка. Снимите галочку, чтобы скрыть тайл.
          </div>
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={handleDragEnd}
          >
            <SortableContext
              items={tilesSettings.order}
              strategy={verticalListSortingStrategy}
            >
              {tilesSettings.order
                .map(id => tilesConfig.find(tile => tile.id === id))
                .filter((tile): tile is NonNullable<typeof tile> => tile !== undefined)
                .map(tile => (
                  <SortableTileItem
                    key={tile.id}
                    id={tile.id}
                    title={tile.title}
                    visible={tilesSettings.visible[tile.id] !== false}
                    onToggle={toggleVisibility}
                    disabled={false}
                  />
                ))}
            </SortableContext>
          </DndContext>
        </List>

        {/* Actions Section */}
        <div style={{ padding: '24px 16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <Button color="primary" block size="large" onClick={handleSave}>
            Сохранить настройки
          </Button>
          <Button block size="large" onClick={handleReset}>
            Сбросить
          </Button>
        </div>
      </div>
    </div>
  );
}
