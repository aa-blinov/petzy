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
import { getApiErrorMessage } from '../utils/apiError';

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
  const { eventTypes, eventTypesByKey } = useEventTypes();
  const settings = useMemo<FormSettings>(() => pet.form_defaults ?? {}, [pet.form_defaults]);
  const [editing, setEditing] = useState<Row | null>(null);
  const [text, setText] = useState('');
  /** What the field was opened with: the panel's close button asks before dropping anything else. */
  const [openedText, setOpenedText] = useState('');
  const [saving, setSaving] = useState(false);

  // The sections follow the list of types the person already sees elsewhere in the app (EventTypesSettings puts
  // the family's own types first), and a type that is gone from the registry goes last. They used to follow the
  // order of the keys in the saved object, which is the order values happened to be remembered in: the same
  // pet showed its sections in another order after the first edit.
  const groups = useMemo(() => {
    const out: { typeKey: string; label: string; rows: Row[] }[] = [];
    const keys = [...eventTypes.map((t) => t.key), ...Object.keys(settings).filter((k) => !eventTypesByKey[k])];
    for (const typeKey of keys) {
      const values = settings[typeKey];
      if (!values) continue;
      const type = eventTypesByKey[typeKey];
      const rows: Row[] = Object.entries(values).map(([field, value]) => {
        const def = type?.fields.find((f) => f.name === field);
        return { typeKey, typeLabel: type?.label ?? 'Удалённый вид записи', field, label: def?.label ?? field, value, def };
      });
      if (rows.length) out.push({ typeKey, label: type?.label ?? 'Удалённый вид записи', rows });
    }
    return out;
  }, [settings, eventTypesByKey, eventTypes]);

  // The whole set is sent each time and replaces the old one: a change is a copy of what is there with one value changed.
  const persist = async (next: FormSettings, done: string) => {
    setSaving(true);
    try {
      const saved = await petsService.saveFormDefaults(pet._id, next);
      queryClient.setQueryData<Pet[]>(['pets'], (pets) => pets?.map((p) => (p._id === pet._id ? { ...p, form_defaults: saved } : p)));
      showToast.success(done);
      return true;
    } catch (error) {
      // What the server refused is said, as the account rows say it: «Не удалось сохранить» on its own left
      // the person with nothing to act on (a field the server won't take, an account without access).
      showToast.failure(getApiErrorMessage(error, 'Не удалось сохранить'));
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
    if (saving) return;
    setEditing(row);
    const start = row.def?.type === 'number' ? row.value.replace('.', ',') : row.value;
    setText(start);
    setOpenedText(start);
  };

  /** Closing the panel with something typed in asks first: a tap on the background used to drop it in silence. */
  const closeEditing = async () => {
    if (text === openedText) {
      setEditing(null);
      return;
    }
    const sure = await Dialog.confirm({
      content: 'Введённое значение не сохранится',
      confirmText: 'Закрыть',
      cancelText: 'Остаться',
    });
    if (sure) setEditing(null);
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
      content: 'Забыть все значения по умолчанию этого питомца? Это коснётся всех, у кого есть к нему доступ. Новые записи будут открываться пустыми',
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
          <h1 className="display-headline" style={{ fontSize: 'var(--text-xxl)', margin: 0 }}>Значения по умолчанию</h1>
          <p style={{ margin: 'var(--spacing-sm) 0 0', fontSize: 'var(--text-sm)', lineHeight: 1.5, color: 'var(--app-text-secondary)' }}>
            Питомец: {pet.name}. Подставляются в новые записи этого питомца и одинаковы для всех, у кого есть к нему доступ. Запомнить значение проще всего в форме новой записи, под полем: «Запомнить для этого питомца». Здесь их можно поправить или забыть. У обязательного поля с вариантами, когда значение не запомнено, выбран первый вариант
          </p>
        </div>

        <div style={{ padding: '0 var(--spacing-md)' }}>
          {groups.length === 0 ? (
            <div className="card-soft" style={{ padding: '16px', color: 'var(--app-text-secondary)', fontSize: 'var(--text-md)', lineHeight: 1.5 }}>
              Пока ничего не запомнено, и новые записи этого питомца открываются пустыми. У обязательных полей с вариантами выбран первый вариант
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
                        disabled={!row.def || saving}
                        style={{ flex: 1, minWidth: 0, minHeight: 'var(--touch-min)', display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 'var(--spacing-2xs)', padding: '12px 16px', background: 'none', border: 'none', textAlign: 'left', font: 'inherit', cursor: row.def ? 'pointer' : 'default', color: 'var(--app-text-primary)' }}
                      >
                        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--app-text-secondary)' }}>{row.label}</span>
                        <span style={{ fontSize: 'var(--text-md)', fontWeight: 600, overflowWrap: 'anywhere' }}>{shown(row)}</span>
                        {/* A field that is no longer in the type keeps its value, and there is nothing to edit it
                            with: said here, so the inert button and the latin name need no guessing. */}
                        {!row.def && (
                          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--app-text-secondary)' }}>
                            Поля больше нет в этом виде записи, значение можно только забыть
                          </span>
                        )}
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
              disabled={saving}
              style={{ width: '100%', minHeight: 'var(--touch-min)', margin: 'var(--spacing-sm) 0 var(--spacing-xl)', background: 'none', border: 'none', font: 'inherit', fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--app-danger-text, var(--app-danger-color))', cursor: 'pointer' }}
            >
              Забыть всё для этого питомца
            </button>
          )}
        </div>
      </div>

      {/* A choice is picked from its own options; a word or a number is typed. */}
      {editing && isSelect && (
        <Picker
          visible
          // The wheel says nothing about what it is choosing: a field's choices came up under no heading at
          // all, so the person picked a value before knowing whose it was.
          title={editing ? `${editing.typeLabel}: ${editing.label}` : ''}
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
      <Popup visible={!!editing && !isSelect} bodyStyle={{ borderTopLeftRadius: 16, borderTopRightRadius: 16, padding: 16 }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--spacing-sm)' }}>
          <label
            htmlFor="default-value"
            style={{ flex: 1, minWidth: 0, fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--app-text-primary)', paddingTop: 12 }}
          >
            {editing ? `${editing.typeLabel}: ${editing.label}` : ''}
          </label>
          <button
            type="button"
            className="tap-feedback"
            aria-label="Закрыть без сохранения"
            onClick={() => void closeEditing()}
            style={{ width: 'var(--touch-min)', height: 'var(--touch-min)', flexShrink: 0, margin: 'calc(var(--touch-min) / -2) -8px -8px 0', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'none', border: 'none', color: 'var(--app-text-secondary)', cursor: 'pointer' }}
          >
            <X size={18} strokeWidth={2.2} aria-hidden />
          </button>
        </div>
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
