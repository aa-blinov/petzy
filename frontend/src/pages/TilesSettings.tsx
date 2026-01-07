import { useCallback, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, List, Switch, Toast } from 'antd-mobile';
import { useTilesSettings } from '../hooks/useTilesSettings';
import { tilesConfig } from '../utils/tilesConfig';
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

export function TilesSettings() {
  const navigate = useNavigate();
  const mountedRef = useRef(true);
  const { tilesSettings, updateOrder, toggleVisibility, resetSettings } = useTilesSettings();

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
    Toast.show({
      icon: 'success',
      content: 'Настройки тайлов сохранены',
      duration: 1000,
    });
    setTimeout(() => {
      if (mountedRef.current) {
        navigate('/settings');
      }
    }, 1000);
  }, [navigate]);

  const handleReset = useCallback(() => {
    const confirmed = window.confirm('Вы уверены, что хотите сбросить настройки тайлов к значениям по умолчанию?');
    if (confirmed) {
      try {
        resetSettings();
        Toast.show({
          icon: 'success',
          content: 'Настройки тайлов сброшены',
          duration: 1000,
        });
      } catch (err) {
        Toast.show({
          icon: 'fail',
          content: 'Ошибка при сбросе настроек',
        });
      }
    }
  }, [resetSettings]);

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
          <h2 style={{ color: 'var(--app-text-color)', fontSize: '24px', fontWeight: 600, margin: 0 }}>Настройка тайлов дневника</h2>
          <p style={{ margin: '8px 0 0 0', fontSize: '14px', color: 'var(--adm-color-weak)' }}>
            Перетащите тайлы для изменения порядка. Снимите галочку, чтобы скрыть тайл.
          </p>
        </div>

        {/* Tiles Drag and Drop */}
        <List mode="card">
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={handleDragEnd}
          >
            <SortableContext
              items={tilesSettings.order}
              strategy={verticalListSortingStrategy}
            >
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
                    disabled={tile.id === 'history'}
                  />
                );
              })}
            </SortableContext>
          </DndContext>
        </List>

        {/* Action Buttons */}
        <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <Button block color="primary" size="large" onClick={handleSave}>
            Сохранить
          </Button>
          <Button block color="default" size="large" onClick={handleReset}>
            Сбросить к значениям по умолчанию
          </Button>
        </div>
      </div>
    </div>
  );
}

