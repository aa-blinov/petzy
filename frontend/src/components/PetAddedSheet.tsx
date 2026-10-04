import { createElement } from 'react';
import { Popup } from 'antd-mobile';

import { DraggableSheetBody } from './DraggableSheetBody';
import type { Pet } from '../services/pets.service';
import { useEventTypes } from '../hooks/useEventTypes';
import { defaultTilesFor, getSpecies } from '../utils/species';

/**
 * What a person sees right after adding a pet: it is theirs now, here is what its «+» starts with, and the two things worth doing
 * next. The same turn as the end of the first-pet onboarding, shorter, for the second pet and the third.
 */
export function PetAddedSheet({
  visible,
  pet,
  onClose,
  onRecord,
  onLook,
}: {
  visible: boolean;
  pet: Pet | null;
  onClose: () => void;
  /** Straight to the first record: the pet's first event, with its form. */
  onRecord: (eventKey: string, eventLabel: string) => void;
  onLook: () => void;
}) {
  const { eventTypesByKey } = useEventTypes();
  if (!pet) return null;
  const species = getSpecies(pet.species);
  const starter = defaultTilesFor(pet.species).order;
  const labels = starter.map((key) => eventTypesByKey[key]?.label).filter((l): l is string => !!l);
  const first = starter[0];
  const firstLabel = eventTypesByKey[first]?.label ?? 'событие';

  return (
    <Popup visible={visible} onMaskClick={onClose} position="bottom" bodyStyle={{ background: 'transparent' }}>
      <DraggableSheetBody visible={visible} onClose={onClose} maxHeight="85vh" label={`${pet.name} добавлен`}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, margin: '4px 4px var(--spacing-md)' }}>
          <span
            aria-hidden
            style={{ width: 56, height: 56, flexShrink: 0, borderRadius: 'var(--radius-md)', background: species.gradient, color: 'var(--app-text-on-dark)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          >
            {createElement(species.icon, { size: 30, strokeWidth: 2 })}
          </span>
          <h2 style={{ margin: 0, fontSize: '1.25rem', lineHeight: 1.2, color: 'var(--app-text-primary)', overflowWrap: 'anywhere' }}>
            {pet.name} теперь в Petzy
          </h2>
        </div>

        <p style={{ margin: '0 4px var(--spacing-lg)', color: 'var(--app-text-secondary)', lineHeight: 1.5 }}>
          В окне «+» уже есть: {labels.join(', ').toLowerCase()}. Остальное добавляется в «События питомца», когда понадобится
        </p>

        <button
          type="button"
          className="tap-feedback"
          onClick={() => onRecord(first, firstLabel)}
          style={{ width: '100%', minHeight: 'var(--touch-min)', border: 'none', borderRadius: 'var(--radius-md)', background: 'var(--app-primary-fill, var(--app-accent))', color: 'var(--app-text-on-dark)', fontFamily: 'inherit', fontSize: 'var(--text-md)', fontWeight: 600, cursor: 'pointer' }}
        >
          Записать: {firstLabel.toLowerCase()}
        </button>
        <button
          type="button"
          className="tap-feedback"
          onClick={onLook}
          style={{ width: '100%', minHeight: 'var(--touch-min)', marginTop: 'var(--spacing-md)', borderRadius: 'var(--radius-md)', border: '1px solid var(--app-border-color)', background: 'var(--app-card-background)', color: 'var(--app-text-primary)', fontFamily: 'inherit', fontSize: 'var(--text-md)', fontWeight: 600, cursor: 'pointer' }}
        >
          Оформить карточку
        </button>
        <button
          type="button"
          className="tap-feedback"
          onClick={onClose}
          style={{ width: '100%', minHeight: 'var(--touch-min)', margin: 'var(--spacing-sm) 0 var(--spacing-md)', background: 'none', border: 'none', font: 'inherit', fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--app-text-secondary)', cursor: 'pointer' }}
        >
          Готово
        </button>
      </DraggableSheetBody>
    </Popup>
  );
}
