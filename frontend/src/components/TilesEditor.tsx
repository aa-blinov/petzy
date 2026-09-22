/**
 * The one tile editor: drag to reorder, switch to show/hide.
 *
 * There used to be two — this list inside the pet form, and a copy on
 * the standalone /tiles-settings page. The copy read and wrote a
 * device-wide `tilesSettings` key in localStorage, while every consumer
 * (the quick-add sheet, the history filter chips) reads the pet's own
 * `tiles_settings` from the API. Reordering or hiding a tile on that
 * page therefore changed nothing anyone displayed. One component over
 * one store removes the class of bug rather than the instance.
 *
 * Settings are per pet on purpose: which routines matter differs by
 * animal — a litter tray for a cat, asthma for the one that has it.
 * Changes save immediately, one PUT per toggle or drop.
 */

import { List, Switch } from 'antd-mobile';
import { GripVertical } from 'lucide-react';
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';

import { usePetTilesSettings } from '../hooks/usePetTilesSettings';
import { useEventTypes } from '../hooks/useEventTypes';
import { buildTiles } from '../utils/tilesConfig';

function SortableTileItem({
  id,
  title,
  visible,
  onToggle,
}: {
  id: string;
  title: string;
  visible: boolean;
  onToggle: (id: string, visible: boolean) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });

  return (
    <div
      ref={setNodeRef}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.5 : 1,
        zIndex: isDragging ? 1000 : 'auto',
        position: 'relative',
      }}
    >
      <List.Item
        prefix={
          <div
            {...attributes}
            {...listeners}
            aria-label={`Переместить ${title}`}
            style={{
              cursor: 'grab',
              color: 'var(--app-text-tertiary)',
              paddingRight: 8,
              touchAction: 'none',
              display: 'flex',
            }}
          >
            <GripVertical size={20} strokeWidth={2} style={{ display: 'block' }} />
          </div>
        }
        extra={
          <Switch
            checked={visible}
            onChange={(checked) => onToggle(id, checked)}
            aria-label={`Показывать ${title}`}
          />
        }
      >
        {title}
      </List.Item>
    </div>
  );
}

export function TilesEditor({ petId, mode = 'plain' }: { petId: string; mode?: 'plain' | 'card' }) {
  const { tilesSettings, updateOrder, toggleVisibility } = usePetTilesSettings(petId);
  const { eventTypes } = useEventTypes();

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  // Build from the registry (+ medications), not from `order`.
  //
  // Both old editors mapped over `tilesSettings.order`, so a tile the
  // pet's stored order didn't mention simply wasn't listed — it could be
  // neither hidden nor moved, even though the app still displays it
  // (absent from `order` sorts last, absent from `visible` counts as
  // shown). Adding a record type would have silently produced exactly
  // that. Sorting a complete list by `order` keeps the stored sequence
  // and appends anything new at the end, which is where it renders.
  const tiles = buildTiles(eventTypes)
    .filter((t) => t.isTile !== false)
    .sort((a, b) => {
      const ai = tilesSettings.order.indexOf(a.id);
      const bi = tilesSettings.order.indexOf(b.id);
      return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
    });

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    // Reorder the ids as currently shown, so a drop lands where the user
    // sees it even when the stored order was missing entries.
    const ids = tiles.map((t) => t.id);
    const from = ids.indexOf(active.id as string);
    const to = ids.indexOf(over.id as string);
    if (from === -1 || to === -1) return;

    // Ids the editor doesn't show (medications) keep their stored place.
    const hidden = tilesSettings.order.filter((id) => !ids.includes(id));
    updateOrder([...arrayMove(ids, from, to), ...hidden]);
  };

  return (
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
      <SortableContext items={tiles.map((t) => t.id)} strategy={verticalListSortingStrategy}>
        <List mode={mode === 'card' ? 'card' : undefined} style={{ '--background-color': 'transparent' } as React.CSSProperties}>
          {tiles.map((tile) => (
            <SortableTileItem
              key={tile.id}
              id={tile.id}
              title={tile.title}
              visible={tilesSettings.visible[tile.id] !== false}
              onToggle={toggleVisibility}
            />
          ))}
        </List>
      </SortableContext>
    </DndContext>
  );
}
