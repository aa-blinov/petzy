import { useMemo, useState } from 'react';
import { Dialog, Input, Picker, Popup } from 'antd-mobile';
import { X } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { petsService, type Pet } from '../services/pets.service';
import type { EventTypeField } from '../services/eventTypes.service';
import type { FormSettings } from '../utils/formsConfig';
import { useEventTypes } from '../hooks/useEventTypes';
import { usePet } from '../hooks/usePet';
import { NoPetState } from '../components/NoPetState';
import { SpinnerButton } from '../components/SpinnerButton';
import { showToast } from '../utils/toast';

/** One remembered value, found again in the type it belongs to (it may be gone: a type or a field deleted since). */
interface Row {
  typeKey: string;
  typeLabel: string;
  field: string;
  label: string;
  value: string;
  def?: EventTypeField;
}

/** The text of a value as the person would read it: the label of a choice, a number with a comma. */
function shown(row: Row): string {
  if (row.def?.type === 'select') return row.def.options?.find((o) => o.value === row.value)?.text ?? row.value;
  if (row.def?.type === 'number') return row.value.replace('.', ',');
  return row.value;
}

/** «Значения по умолчанию»: what is remembered for the selected pet, by record type, to correct or to forget. Remembering
 *  itself is done where it is natural: under a field of a new record. The values are the pet's, not the person's: its food
 *  or drops are the same for everyone who feeds it. */
export function FormDefaults() {
  const { getSelectedPet } = usePet();
  if (!getSelectedPet) return <NoPetState what="Значения по умолчанию" />;
  // Keyed by the pet: choosing another pet in the switcher opens that pet's own values.
  return <FormDefaultsFor key={getSelectedPet._id} pet={getSelectedPet} />;
}

function FormDefaultsFor({ pet }: { pet: Pet }) {
  const queryClient = useQueryClient();
  const { eventTypesByKey } = useEventTypes();
  const settings = useMemo<FormSettings>(() => pet.form_defaults ?? {}, [pet.form_defaults]);
  const [editing, setEditing] = useState<Row | null>(null);
  const [text, setText] = useState('');
  const [saving, setSaving] = useState(false);

  const groups = useMemo(() => {
    const out: { typeKey: string; label: string; rows: Row[] }[] = [];
    for (const [typeKey, values] of Object.entries(settings)) {
      const type = eventTypesByKey[typeKey];
      const rows: Row[] = Object.entries(values).map(([field, value]) => {
        const def = type?.fields.find((f) => f.name === field);
        return { typeKey, typeLabel: type?.label ?? 'Удалённый вид записи', field, label: def?.label ?? field, value, def };
      });
      if (rows.length) out.push({ typeKey, label: type?.label ?? 'Удалённый вид записи', rows });
    }
    return out;
  }, [settings, eventTypesByKey]);

  // The whole set is sent each time and replaces the old one: a change is a copy of what is there with one value changed.
  const persist = async (next: FormSettings, done: string) => {
    setSaving(true);
    try {
      const saved = await petsService.saveFormDefaults(pet._id, next);
      queryClient.setQueryData<Pet[]>(['pets'], (pets) => pets?.map((p) => (p._id === pet._id ? { ...p, form_defaults: saved } : p)));
      showToast.success(done);
      return true;
    } catch {
      showToast.failure('Не удалось сохранить');
      return false;
    } finally {
      setSaving(false);
    }
  };

  const change = (row: Row, value: string | null) => {
    const next: FormSettings = { ...settings, [row.typeKey]: { ...settings[row.typeKey] } };
    if (value === null || value.trim() === '') delete next[row.typeKey][row.field];
    else next[row.typeKey][row.field] = value.trim();
    if (!Object.keys(next[row.typeKey]).length) delete next[row.typeKey];
    return persist(next, value === null || value.trim() === '' ? 'Забыто' : 'Сохранено');
  };

  const open = (row: Row) => {
    setEditing(row);
    setText(row.def?.type === 'number' ? row.value.replace('.', ',') : row.value);
  };

  const saveText = async () => {
    if (!editing) return;
    let value = text.trim();
    if (editing.def?.type === 'number') {
      const n = Number(value.replace(/\s/g, '').replace(',', '.'));
      if (value === '' || !Number.isFinite(n)) {
        showToast.failure('Введите число, например 195,5');
        return;
      }
      value = String(n);
    }
    if (await change(editing, value)) setEditing(null);
  };

  const forgetAll = async () => {
    const confirmed = await Dialog.confirm({
      content: `Забыть все значения по умолчанию для ${pet.name}? Новые записи будут открываться пустыми`,
      confirmText: 'Забыть',
      cancelText: 'Оставить',
    });
    if (confirmed) await persist({}, 'Забыто');
  };

  const isSelect = editing?.def?.type === 'select';

  return (
    <div className="page-container">
      <div className="max-width-container">
        <div className="safe-area-padding" style={{ marginBottom: 'var(--spacing-lg)' }}>
          <h1 style={{ color: 'var(--app-text-color)', fontSize: 'var(--text-xxl)', fontWeight: 600, margin: 0 }}>Значения по умолчанию</h1>
          <p style={{ margin: 'var(--spacing-sm) 0 0', fontSize: 'var(--text-sm)', lineHeight: 1.5, color: 'var(--app-text-secondary)' }}>
            Питомец: {pet.name}. Подставляются в новые записи этого питомца и одинаковы для всех, у кого есть к нему доступ. Запомнить значение проще всего в форме новой записи, под полем: «Запомнить для» и имя питомца. Здесь их можно поправить или забыть. Там, где есть выбор из вариантов, без запомненного значения выбран первый
          </p>
        </div>

        <div style={{ padding: '0 var(--spacing-md)' }}>
          {groups.length === 0 ? (
            <div className="card-soft" style={{ padding: '16px', color: 'var(--app-text-secondary)', fontSize: 'var(--text-md)', lineHeight: 1.5 }}>
              Для {pet.name} пока ничего не запомнено, и новые записи открываются пустыми
            </div>
          ) : (
            groups.map((g) => (
              <section key={g.typeKey} style={{ marginBottom: 'var(--spacing-md)' }}>
                <h2 className="section-header" style={{ marginBottom: 'var(--spacing-sm)' }}>
                  {g.label}
                </h2>
                <div className="card-soft" style={{ overflow: 'hidden' }}>
                  {g.rows.map((row, i) => (
                    <div key={row.field} style={{ display: 'flex', alignItems: 'center', borderTop: i ? '1px solid var(--app-border-color)' : 'none' }}>
                      <button
                        type="button"
                        className="tap-feedback"
                        onClick={() => open(row)}
                        disabled={!row.def}
                        style={{ flex: 1, minWidth: 0, minHeight: 'var(--touch-min)', display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: '2px', padding: '12px 16px', background: 'none', border: 'none', textAlign: 'left', font: 'inherit', cursor: row.def ? 'pointer' : 'default', color: 'var(--app-text-primary)' }}
                      >
                        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--app-text-secondary)' }}>{row.label}</span>
                        <span style={{ fontSize: 'var(--text-md)', fontWeight: 600, overflowWrap: 'anywhere' }}>{shown(row)}</span>
                      </button>
                      <button
                        type="button"
                        className="tap-feedback"
                        aria-label={`Забыть: ${g.label}, ${row.label}`}
                        disabled={saving}
                        onClick={() => void change(row, null)}
                        style={{ width: 'var(--touch-min)', height: 'var(--touch-min)', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'none', border: 'none', color: 'var(--app-text-secondary)', cursor: 'pointer' }}
                      >
                        <X size={18} strokeWidth={2.2} aria-hidden />
                      </button>
                    </div>
                  ))}
                </div>
              </section>
            ))
          )}

          {groups.length > 0 && (
            <button
              type="button"
              className="tap-feedback"
              onClick={() => void forgetAll()}
              style={{ width: '100%', minHeight: 'var(--touch-min)', margin: 'var(--spacing-sm) 0 var(--spacing-xl)', background: 'none', border: 'none', font: 'inherit', fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--app-danger-text, var(--app-danger-color))', cursor: 'pointer' }}
            >
              Забыть всё для {pet.name}
            </button>
          )}
        </div>
      </div>

      {/* A choice is picked from its own options; a word or a number is typed. */}
      {editing && isSelect && (
        <Picker
          visible
          columns={[(editing.def?.options ?? []).map((o) => ({ label: o.text, value: o.value }))]}
          value={[editing.value]}
          onClose={() => setEditing(null)}
          onConfirm={async (val) => {
            if (val[0] && (await change(editing, String(val[0])))) setEditing(null);
          }}
          cancelText="Отмена"
          confirmText="Готово"
        />
      )}
      <Popup visible={!!editing && !isSelect} onMaskClick={() => setEditing(null)} bodyStyle={{ borderTopLeftRadius: 16, borderTopRightRadius: 16, padding: 16 }}>
        <label htmlFor="default-value" style={{ display: 'block', fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--app-text-primary)', marginBottom: 8 }}>
          {editing ? `${editing.typeLabel}: ${editing.label}` : ''}
        </label>
        <Input
          id="default-value"
          value={text}
          onChange={setText}
          onEnterPress={() => void saveText()}
          placeholder="Значение"
          maxLength={200}
          inputMode={editing?.def?.type === 'number' ? 'decimal' : undefined}
          style={{ '--font-size': 'var(--text-md)', border: '1px solid var(--app-border-color)', borderRadius: 'var(--radius-md)', padding: '0 12px', minHeight: 'var(--touch-min)' } as React.CSSProperties}
        />
        <div style={{ marginTop: 12 }}>
          <SpinnerButton type="button" block loading={saving} onClick={() => void saveText()}>
            Сохранить
          </SpinnerButton>
        </div>
      </Popup>
    </div>
  );
}
