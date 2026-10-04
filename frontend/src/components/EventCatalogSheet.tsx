import { createElement, useMemo, useState } from 'react';
import { Popup } from 'antd-mobile';
import { Plus, Search } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import { DraggableSheetBody } from './DraggableSheetBody';
import type { EventType } from '../services/eventTypes.service';
import { EVENT_CATEGORIES } from '../utils/tilesConfig';
import { getEventIcon } from '../utils/iconRegistry';
import { pastelColorMap } from '../utils/constants';
import { hapticFeedback } from '../utils/haptic';

/** What a record of this type asks for, in a line: «Вес корма (г)», or just a mark that it happened. */
function asks(type: EventType): string {
  const labels = type.fields.map((f) => f.label);
  return labels.length ? labels.join(', ') : 'Просто отметка';
}

interface Group {
  key: string;
  title: string;
  types: EventType[];
}

/**
 * Everything the app can record that this pet's «+» does not offer yet, to choose from: first what suits its kind of animal,
 * then by group. A long catalogue is searched, not scrolled to the end; what is added leaves the list, so it only ever shows
 * what is left to add.
 */
export function EventCatalogSheet({
  visible,
  onClose,
  types,
  suggested,
  speciesLabel,
  onAdd,
}: {
  visible: boolean;
  onClose: () => void;
  /** The types not on the «+» yet. */
  types: EventType[];
  /** Keys that suit the pet's kind of animal, in the order to offer them. */
  suggested: string[];
  speciesLabel: string;
  onAdd: (key: string) => void;
}) {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const needle = query.trim().toLowerCase();

  const groups = useMemo<Group[]>(() => {
    const found = needle ? types.filter((t) => `${t.label} ${asks(t)}`.toLowerCase().includes(needle)) : types;
    if (needle) return found.length ? [{ key: 'found', title: 'Найдено', types: found }] : [];
    const byKey = new Map(found.map((t) => [t.key, t]));
    const first = suggested.map((k) => byKey.get(k)).filter((t): t is EventType => !!t);
    const taken = new Set(first.map((t) => t.key));
    const out: Group[] = [];
    if (first.length) out.push({ key: 'suggested', title: `Подойдёт для ${speciesLabel}`, types: first });
    for (const category of EVENT_CATEGORIES) {
      const inGroup = found.filter((t) => !taken.has(t.key) && (category.key === 'custom' ? !t.is_builtin : t.category === category.key));
      if (inGroup.length) out.push({ key: category.key, title: category.label, types: inGroup });
    }
    return out;
  }, [types, suggested, speciesLabel, needle]);

  return (
    <Popup visible={visible} onMaskClick={onClose} position="bottom" bodyStyle={{ background: 'transparent' }}>
      <DraggableSheetBody visible={visible} onClose={onClose} maxHeight="88vh" label="Добавить событие">
        <h2 className="section-header" style={{ marginBottom: 'var(--spacing-md)', paddingLeft: 4, fontSize: '1.125rem' }}>
          Добавить событие
        </h2>

        <label style={{ position: 'relative', display: 'block', marginBottom: 'var(--spacing-md)' }}>
          <span className="sr-only">Найти событие</span>
          <Search size={18} strokeWidth={2} aria-hidden style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--app-text-secondary)' }} />
          <input
            type="text"
            inputMode="search"
            enterKeyHint="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Найти событие"
            autoComplete="off"
            style={{
              width: '100%',
              boxSizing: 'border-box',
              minHeight: 'var(--touch-min)',
              padding: '0 12px 0 38px',
              border: '1px solid var(--app-border-color)',
              borderRadius: 'var(--radius-md)',
              background: 'var(--app-page-background)',
              color: 'var(--app-text-primary)',
              fontFamily: 'inherit',
              fontSize: 'var(--text-md)',
            }}
          />
        </label>

        {groups.length === 0 && (
          <p style={{ margin: '0 4px var(--spacing-md)', color: 'var(--app-text-secondary)' }}>
            {needle ? 'Ничего не найдено. Можно создать своё событие' : 'Всё, что есть, уже в окне «+». Можно создать своё событие'}
          </p>
        )}

        {groups.map((group) => (
          <section key={group.key} aria-label={group.title} style={{ marginBottom: 'var(--spacing-md)' }}>
            <h3 style={{ margin: '0 4px 6px', fontSize: 'var(--text-xs)', fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase', color: 'var(--app-text-secondary)' }}>
              {group.title}
            </h3>
            <div className="card-soft" style={{ overflow: 'hidden' }}>
              {group.types.map((type, i) => {
                return (
                  <button
                    key={type.key}
                    type="button"
                    className="tap-feedback"
                    aria-label={`Добавить: ${type.label}`}
                    onClick={() => {
                      hapticFeedback('light');
                      onAdd(type.key);
                    }}
                    style={{
                      width: '100%',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 12,
                      minHeight: 56,
                      padding: '8px 12px',
                      background: 'none',
                      border: 'none',
                      borderTop: i ? '1px solid var(--app-border-color)' : 'none',
                      color: 'var(--app-text-primary)',
                      font: 'inherit',
                      textAlign: 'left',
                      cursor: 'pointer',
                    }}
                  >
                    <span aria-hidden style={{ width: 40, height: 40, flexShrink: 0, borderRadius: 'var(--radius-md)', background: pastelColorMap[type.color] ?? 'var(--tile-blue)', color: 'var(--app-text-on-tile)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      {createElement(getEventIcon(type.icon), { size: 20, strokeWidth: 2 })}
                    </span>
                    <span style={{ flex: 1, minWidth: 0 }}>
                      <span style={{ display: 'block', fontWeight: 600, overflowWrap: 'anywhere' }}>{type.label}</span>
                      <span style={{ display: 'block', fontSize: 'var(--text-xs)', color: 'var(--app-text-secondary)', overflowWrap: 'anywhere' }}>{asks(type)}</span>
                    </span>
                    <Plus size={20} strokeWidth={2.2} aria-hidden style={{ color: 'var(--app-accent-deep)', flexShrink: 0 }} />
                  </button>
                );
              })}
            </div>
          </section>
        ))}

        <button
          type="button"
          className="tap-feedback"
          onClick={() => {
            onClose();
            navigate('/event-types/new');
          }}
          style={{ width: '100%', minHeight: 'var(--touch-min)', margin: '0 0 var(--spacing-md)', background: 'none', border: 'none', font: 'inherit', fontSize: 'var(--text-md)', fontWeight: 600, color: 'var(--app-accent-deep)', cursor: 'pointer' }}
        >
          Создать своё событие
        </button>
      </DraggableSheetBody>
    </Popup>
  );
}
