/**
 * «События питомца»: which records the pet's «+» offers and in what order. The one place for it, and it is the pet's own:
 * a litter tray for a cat, a water change for a fish.
 *
 * The list is what is on the «+», in its order, with a handle to drag and a cross to take one off. The rest of the catalogue
 * is not a wall of switches but a sheet to pick from («Добавить событие»), searched and grouped, with what suits this kind of
 * animal first. Every change is saved at once, as it is made.
 */
import { createElement, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Dialog } from 'antd-mobile';
import { GripVertical, LayoutGrid, Plus, X } from 'lucide-react';
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import { SortableContext, arrayMove, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';

import { usePet } from '../hooks/usePet';
import { usePetTilesSettings } from '../hooks/usePetTilesSettings';
import { useEventTypes } from '../hooks/useEventTypes';
import { EmptyState } from '../components/EmptyState';
import { EventCatalogSheet } from '../components/EventCatalogSheet';
import type { EventType } from '../services/eventTypes.service';
import { buildTiles, byTileOrder, isTileShown } from '../utils/tilesConfig';
import { defaultTilesFor, getSpecies } from '../utils/species';
import { getEventIcon } from '../utils/iconRegistry';
import { pastelColorMap } from '../utils/constants';
import { showToast } from '../utils/toast';

function Row({ type, onRemove }: { type: EventType; onRemove: () => void }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: type.key });
  return (
    <div
      ref={setNodeRef}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.6 : 1,
        zIndex: isDragging ? 10 : 'auto',
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        minHeight: 56,
        background: 'var(--app-card-background)',
        borderTop: '1px solid var(--app-border-color)',
      }}
    >
      <button
        type="button"
        {...attributes}
        {...listeners}
        aria-label={`Переместить: ${type.label}`}
        style={{ width: 44, height: 56, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'none', border: 'none', color: 'var(--app-text-tertiary)', cursor: 'grab', touchAction: 'none' }}
      >
        <GripVertical size={20} strokeWidth={2} aria-hidden />
      </button>
      <span aria-hidden style={{ width: 36, height: 36, flexShrink: 0, borderRadius: 'var(--radius-md)', background: pastelColorMap[type.color] ?? 'var(--tile-blue)', color: 'var(--app-text-on-tile)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {/* A fixed set of module-level icons: createElement, not a component made during render (see PetImage). */}
        {createElement(getEventIcon(type.icon), { size: 18, strokeWidth: 2 })}
      </span>
      <span style={{ flex: 1, minWidth: 0, padding: '0 12px', fontWeight: 600, overflowWrap: 'anywhere' }}>{type.label}</span>
      <button
        type="button"
        className="tap-feedback"
        aria-label={`Убрать из окна «+»: ${type.label}`}
        onClick={onRemove}
        style={{ width: 'var(--touch-min)', height: 'var(--touch-min)', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'none', border: 'none', color: 'var(--app-text-secondary)', cursor: 'pointer' }}
      >
        <X size={18} strokeWidth={2.2} aria-hidden />
      </button>
    </div>
  );
}

export function PetEvents() {
  const navigate = useNavigate();
  const { selectedPetId, getSelectedPet } = usePet();
  const { eventTypes } = useEventTypes();
  const { tilesSettings, saveSettings } = usePetTilesSettings(selectedPetId);
  const [catalogOpen, setCatalogOpen] = useState(false);
  // The events are the owner's to set (the server refuses anyone else): a member sees them, not a list that snaps back.
  const readOnly = getSelectedPet?.current_user_is_owner === false;
  const species = getSpecies(getSelectedPet?.species);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const typesByKey = useMemo(() => new Map(eventTypes.map((t) => [t.key, t])), [eventTypes]);
  const shown = useMemo(
    () =>
      byTileOrder(
        buildTiles(eventTypes).filter((t) => t.isTile !== false && isTileShown(tilesSettings, t.id)),
        tilesSettings,
      )
        .map((t) => typesByKey.get(t.id))
        .filter((t): t is EventType => !!t),
    [eventTypes, tilesSettings, typesByKey],
  );
  const shownKeys = shown.map((t) => t.key);
  const offered = useMemo(() => eventTypes.filter((t) => !shownKeys.includes(t.key)), [eventTypes, shownKeys]);

  // What was stored for the types that are not shown (and medications) keeps its place after those that are.
  const withRest = (keys: string[]) => [...keys, ...tilesSettings.order.filter((k) => !keys.includes(k))];

  const handleDragEnd = ({ active, over }: DragEndEvent) => {
    if (!over || active.id === over.id) return;
    const from = shownKeys.indexOf(String(active.id));
    const to = shownKeys.indexOf(String(over.id));
    if (from < 0 || to < 0) return;
    saveSettings({ ...tilesSettings, order: withRest(arrayMove(shownKeys, from, to)) });
  };

  const add = (key: string) => {
    saveSettings({ order: withRest([...shownKeys, key]), visible: { ...tilesSettings.visible, [key]: true } });
    showToast.success(`Добавлено: ${typesByKey.get(key)?.label ?? key}`);
  };

  const remove = (key: string) => saveSettings({ order: withRest(shownKeys), visible: { ...tilesSettings.visible, [key]: false } });

  const resetToKind = async () => {
    const sure = await Dialog.confirm({
      content: `Вернуть набор событий для ${species.forWhom}? Порядок и состав станут такими, какими были у нового питомца`,
      confirmText: 'Вернуть',
      cancelText: 'Оставить',
    });
    if (sure) saveSettings(defaultTilesFor(getSelectedPet?.species));
  };

  return (
    <div className="page-container">
      <div className="max-width-container">
        <div className="safe-area-padding" style={{ marginBottom: 'var(--spacing-lg)' }}>
          <h1 style={{ color: 'var(--app-text-color)', fontSize: 'var(--text-xxl)', fontWeight: 600, margin: 0 }}>События питомца</h1>
          {getSelectedPet && (
            <p style={{ margin: 'var(--spacing-sm) 0 0', fontSize: 'var(--text-sm)', lineHeight: 1.5, color: 'var(--app-text-secondary)' }}>
              Питомец: {getSelectedPet.name}. Что предлагается в окне «+» и в каком порядке. Потяните за ручку, чтобы поменять порядок. Изменения сохраняются сразу
            </p>
          )}
        </div>

        {!selectedPetId ? (
          <EmptyState icon={LayoutGrid} title="Сначала выберите питомца" description="События настраиваются отдельно для каждого питомца" actionLabel="К питомцам" onAction={() => navigate('/pets')} />
        ) : (
          <div style={{ padding: '0 var(--spacing-md)' }}>
            {readOnly && (
              <p role="note" style={{ margin: '0 0 var(--spacing-md)', color: 'var(--app-text-secondary)' }}>
                События меняет владелец питомца
              </p>
            )}
            <div {...(readOnly ? { inert: '' } : {})} style={readOnly ? { opacity: 0.7 } : undefined}>
              <h2 className="section-header" style={{ marginBottom: 'var(--spacing-sm)' }}>
                В окне «+»: {shown.length}
              </h2>
              <div className="card-soft" style={{ overflow: 'hidden' }}>
                {shown.length === 0 ? (
                  <p style={{ margin: 0, padding: 16, color: 'var(--app-text-secondary)' }}>Пока ничего. Добавьте события, которые вы записываете чаще всего</p>
                ) : (
                  <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
                    <SortableContext items={shownKeys} strategy={verticalListSortingStrategy}>
                      <div style={{ marginTop: -1 }}>
                        {shown.map((type) => (
                          <Row key={type.key} type={type} onRemove={() => remove(type.key)} />
                        ))}
                      </div>
                    </SortableContext>
                  </DndContext>
                )}
              </div>

              <button
                type="button"
                className="tap-feedback"
                onClick={() => setCatalogOpen(true)}
                style={{ width: '100%', minHeight: 'var(--touch-min)', marginTop: 'var(--spacing-md)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, borderRadius: 'var(--radius-md)', border: 'none', background: 'var(--app-primary-fill, var(--app-accent))', color: 'var(--app-text-on-dark)', fontFamily: 'inherit', fontSize: 'var(--text-md)', fontWeight: 600, cursor: 'pointer' }}
              >
                <Plus size={18} strokeWidth={2.4} aria-hidden />
                Добавить событие
              </button>

              <button
                type="button"
                className="tap-feedback"
                onClick={() => void resetToKind()}
                style={{ width: '100%', minHeight: 'var(--touch-min)', margin: 'var(--spacing-sm) 0 var(--spacing-xl)', background: 'none', border: 'none', font: 'inherit', fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--app-text-secondary)', cursor: 'pointer' }}
              >
                Вернуть набор для {species.forWhom}
              </button>
            </div>
          </div>
        )}
      </div>

      <EventCatalogSheet
        visible={catalogOpen}
        onClose={() => setCatalogOpen(false)}
        types={offered}
        suggested={species.suggested}
        speciesLabel={species.forWhom}
        onAdd={add}
      />
    </div>
  );
}
