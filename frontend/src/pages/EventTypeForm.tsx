/**
 * Create/edit an event type — the "factory" itself.
 *
 * Kept as plain component state rather than react-hook-form: the field
 * list is a dynamic array with its own per-row shape (options text only
 * shown for `select`), which react-hook-form's typed API doesn't make
 * meaningfully simpler here.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { goBack } from '../utils/navigation';
import { useUnsavedChangesGuard } from '../hooks/useUnsavedChangesGuard';
import { Button, Input, Switch, Selector, TextArea } from 'antd-mobile';
import { Trash2, Plus } from 'lucide-react';

import { showToast } from '../utils/toast';
import { getApiErrorMessage } from '../utils/apiError';
import { useEventTypes, useInvalidateEventTypes } from '../hooks/useEventTypes';
import { useAdmin } from '../hooks/useAdmin';
import { useAuth } from '../hooks/useAuth';
import { eventTypesService, type EventTypeField } from '../services/eventTypes.service';
import { TILE_COLORS, TILE_COLOR_LABELS, pastelColorMap, type TileColor } from '../utils/constants';
import { ICON_OPTIONS } from '../utils/iconRegistry';
import { slugifyFieldName } from '../utils/slugify';
import { FieldError } from '../components/FieldError';
import { fieldNote } from '../components/FieldNote';
import { LoadError } from '../components/LoadError';
import { LoadingSpinner } from '../components/LoadingSpinner';

type FieldType = EventTypeField['type'];

/** A stored number field with the bounds the record form checks: the type of a form that has no inputs for these, so
 *  they are kept as they are rather than quietly dropped by a save. */
type StoredNumberField = EventTypeField & {
  deviation_threshold?: number | null;
};

/** How a number field is bounded, as one line to read under it. */
function boundsText(field: StoredNumberField): string | undefined {
  const parts: string[] = [];
  const from = field.min;
  const to = field.max;
  if (from !== undefined && from !== null) parts.push(`от ${String(from).replace('.', ',')}`);
  if (to !== undefined && to !== null) parts.push(`до ${String(to).replace('.', ',')}`);
  if (!parts.length) return undefined;
  return `Записи принимаются ${parts.join(' ')}, шаг ${String(field.step ?? 1).replace('.', ',')}`;
}

interface FieldDraft {
  key: string; // local React key only, not sent to the API
  name: string;
  label: string;
  type: FieldType;
  required: boolean;
  optionsText: string; // one option per line, only used for type === 'select'
}

const FIELD_TYPE_OPTIONS: { label: string; value: FieldType }[] = [
  { label: 'Текст', value: 'text' },
  { label: 'Число', value: 'number' },
  { label: 'Выбор из списка', value: 'select' },
  { label: 'Многострочный текст', value: 'textarea' },
];

let draftKeySeq = 0;
function newDraftKey() {
  draftKeySeq += 1;
  return `draft_${draftKeySeq}`;
}

/** A real label above a control — a bare placeholder reads as empty, not
 *  as "here's what this is", so every input in the field-builder card
 *  gets one of these instead. */
function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--app-text-tertiary)', marginBottom: '4px' }}>
      {children}
    </div>
  );
}

function fieldsToDrafts(fields: EventTypeField[]): FieldDraft[] {
  return fields.map((f) => ({
    key: newDraftKey(),
    name: f.name,
    label: f.label,
    type: f.type,
    required: f.required,
    optionsText: (f.options ?? []).map((o) => o.text).join('\n'),
  }));
}

export function EventTypeForm() {
  const navigate = useNavigate();
  const { key } = useParams<{ key?: string }>();
  const isEditing = !!key;
  const { eventTypesByKey, isLoading: eventTypesLoading, error: eventTypesError, refetch: refetchEventTypes } = useEventTypes();
  const invalidate = useInvalidateEventTypes();
  const existing = key ? eventTypesByKey[key] : undefined;

  // The right to change a type, checked the same way the list checks it (EventTypesSettings): a built-in type is
  // the same for everybody, so an admin's to change; a custom one is its author's. The form used to open in
  // full for anyone who had the address, and the refusal came only on «Сохранить», after a form of someone
  // else's type had been filled in.
  const { isAdmin } = useAdmin();
  const { username: currentUsername } = useAuth();
  const canEdit = !isEditing
    || (existing ? (existing.is_builtin ? isAdmin : existing.created_by === currentUsername) : false);

  const [label, setLabel] = useState('');
  const [icon, setIcon] = useState('paw');
  const [color, setColor] = useState<TileColor>('blue');
  const [fields, setFields] = useState<FieldDraft[]>([]);
  const [chartKind, setChartKind] = useState<'count' | 'value'>('count');
  const [chartValueName, setChartValueName] = useState('');
  const [chartValueLabel, setChartValueLabel] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [loadedExisting, setLoadedExisting] = useState(!isEditing);
  // What is wrong with the form, by the thing it is wrong about: a message under its own field, not a toast that
  // names no field and is gone by the time it has been looked for.
  const [labelError, setLabelError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, { label?: string; options?: string }>>({});
  const [chartError, setChartError] = useState<string | null>(null);
  // The field the chart was built on is gone: the person is told the chart has to be pointed again instead of one
  // number field quietly taking the graph over.
  const [chartFieldLost, setChartFieldLost] = useState(false);
  const pageRef = useRef<HTMLDivElement>(null);

  // Prefill once the registry has loaded and — if editing — the type is found.
  useEffect(() => {
    if (loadedExisting) return;
    if (eventTypesLoading) return;
    if (!existing) return;

    setLabel(existing.label);
    setIcon(existing.icon);
    setColor(existing.color);
    setFields(fieldsToDrafts(existing.fields));
    setChartKind(existing.chart.kind);
    setChartValueName(existing.chart.value_field ?? '');
    setChartValueLabel(existing.chart.value_label ?? '');
    setLoadedExisting(true);
  }, [loadedExisting, eventTypesLoading, existing]);

  // Unsaved = different from how the form looked once it was ready (empty
  // for a new type, the stored one for an edit).
  const snapshot = JSON.stringify({ label, icon, color, fields, chartKind, chartValueName, chartValueLabel });
  const [saved, setSaved] = useState<string | null>(null);
  useEffect(() => {
    if (loadedExisting && saved === null) setSaved(snapshot);
  }, [loadedExisting, saved, snapshot]);
  const { dialog: leaveDialog, release } = useUnsavedChangesGuard(saved !== null && snapshot !== saved);

  // One resolved ascii name per field draft, kept stable by draft key so
  // the chart-value picker (which needs a name to select) and the save
  // payload (which needs the same names) never compute two different
  // slugs for the same field.
  const resolvedNames = useMemo(() => {
    const used: string[] = [];
    const map: Record<string, string> = {};
    for (const f of fields) {
      const name = f.name || slugifyFieldName(f.label || 'поле', used);
      used.push(name);
      map[f.key] = name;
    }
    return map;
  }, [fields]);

  const numberFields = useMemo(
    () => fields.filter((f) => f.type === 'number').map((f) => ({ ...f, resolvedName: resolvedNames[f.key] })),
    [fields, resolvedNames]
  );

  // If the field backing the chart is deleted or retyped, its resolved
  // name is gone and the chart has nothing to plot. It used to be moved
  // silently onto the first remaining number field, so the history
  // quietly showed another number than the one before. It is emptied
  // instead, and said: the graph has to be pointed at a field again.
  useEffect(() => {
    if (chartValueName && !numberFields.some((f) => f.resolvedName === chartValueName)) {
      setChartValueName('');
      setChartFieldLost(true);
    }
  }, [numberFields, chartValueName]);

  const storedFields = useMemo(
    () => ((existing?.fields ?? []) as StoredNumberField[]),
    [existing]
  );

  const addField = () => {
    setFields((prev) => [
      ...prev,
      { key: newDraftKey(), name: '', label: '', type: 'text', required: false, optionsText: '' },
    ]);
  };

  const updateField = (key: string, patch: Partial<FieldDraft>) => {
    setFields((prev) => prev.map((f) => (f.key === key ? { ...f, ...patch } : f)));
    setFieldErrors((prev) => {
      const next = { ...prev, [key]: { ...prev[key] } };
      for (const prop of Object.keys(patch) as (keyof FieldDraft)[]) {
        if (prop === 'label' && next[key]) next[key].label = undefined;
        if (prop === 'optionsText' && next[key]) next[key].options = undefined;
      }
      return next;
    });
  };

  const removeField = (key: string) => {
    setFields((prev) => prev.filter((f) => f.key !== key));
    setFieldErrors((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  };

  /** The first message on screen takes the eye to it, instead of the person hunting for what a toast named. */
  const scrollToFirstError = () => {
    requestAnimationFrame(() => {
      pageRef.current?.querySelector('.field-error')?.scrollIntoView({ block: 'center' });
    });
  };

  const handleSave = async () => {
    if (!canEdit) return;
    // Each problem is kept against the field it belongs to, so it can be shown there: names are already
    // de-duplicated by slugifyFieldName, so the backend's own uniqueness check never catches a repeated label, but
    // two fields sharing one are indistinguishable everywhere they're actually shown.
    const errors: Record<string, { label?: string; options?: string }> = {};
    let hasLabelProblem = false;
    let hasChartProblem = false;
    const seenLabels = new Set<string>();
    for (const f of fields) {
      const normalized = f.label.trim().toLowerCase();
      if (!normalized) {
        hasLabelProblem = true;
        errors[f.key] = { ...errors[f.key], label: 'У поля должна быть подпись' };
      } else if (seenLabels.has(normalized)) {
        hasLabelProblem = true;
        errors[f.key] = { ...errors[f.key], label: 'Такая подпись уже есть выше' };
      } else {
        seenLabels.add(normalized);
      }
      if (f.type === 'select' && !f.optionsText.trim()) {
        hasLabelProblem = true;
        errors[f.key] = { ...errors[f.key], options: 'Нужен хотя бы один вариант' };
      }
    }
    const nextLabelError = label.trim() ? null : 'Укажите название типа';
    const nextChartError =
      chartKind === 'value'
        ? numberFields.length === 0
          ? 'Для графика по значению нужно хотя бы одно числовое поле'
          : !chartValueName
            ? 'Выберите поле, по которому строить график'
            : null
        : null;
    if (nextChartError) hasChartProblem = true;

    setLabelError(nextLabelError);
    setFieldErrors(errors);
    setChartError(nextChartError);
    if (nextLabelError || hasLabelProblem || hasChartProblem) {
      showToast.failure(nextLabelError ?? 'Проверьте поля и график');
      scrollToFirstError();
      return;
    }

    const resolvedFields: EventTypeField[] = fields.map((f) => {
      const options = f.type === 'select'
        ? f.optionsText.split('\n').map((line) => line.trim()).filter(Boolean).map((text) => ({ value: text, text }))
        : undefined;
      const name = resolvedNames[f.key];
      // The number bounds and the anomaly threshold of a saved field have no input here (the record form, not this one,
      // checks a reading against them), so they travel with the field by name instead of being written off as absent.
      const stored = storedFields.find((s) => s.name === name);
      const carried = f.type === 'number' && stored
        ? { min: stored.min, max: stored.max, step: stored.step, deviation_threshold: stored.deviation_threshold }
        : {};
      return { name, label: f.label.trim(), type: f.type, required: f.required, options, ...carried };
    });

    const payload = {
      label: label.trim(),
      icon,
      color,
      fields: resolvedFields,
      chart: chartKind === 'value'
        ? { kind: 'value' as const, value_field: chartValueName, value_label: chartValueLabel.trim() || 'Значение' }
        : { kind: 'count' as const },
    };

    setIsSaving(true);
    try {
      if (isEditing && key) {
        await eventTypesService.update(key, payload);
      } else {
        await eventTypesService.create(payload);
      }
      invalidate();
      showToast.success(isEditing ? 'Тип события обновлён' : 'Тип события создан');
      release();
      goBack(navigate, '/event-types');
    } catch (error) {
      const message = getApiErrorMessage(error, 'Не удалось сохранить тип события');
      showToast.failure(message);
    } finally {
      setIsSaving(false);
    }
  };

  if (isEditing && eventTypesError) {
    // The registry didn't load: «Тип события не найден» after a failed request sends the person off to create a
    // second copy of a type that is already there.
    return (
      <div className="page-container">
        <div className="safe-area-padding">
          <LoadError what="типы событий" onRetry={() => refetchEventTypes()} />
          <Button block onClick={() => goBack(navigate, '/event-types')}>
            К списку типов
          </Button>
        </div>
      </div>
    );
  }

  if (isEditing && (eventTypesLoading || !loadedExisting)) {
    return <LoadingSpinner />;
  }

  if (isEditing && !existing) {
    return (
      <div style={{ padding: 'var(--spacing-xl)', textAlign: 'center' }}>
        <p>Тип события не найден</p>
        {/* Straight to the list, not back through history: this screen was opened from a link, so «назад»
            led wherever the person came from, which may be a screen this one has nothing to do with. */}
        <Button onClick={() => navigate('/event-types')}>К типам событий</Button>
      </div>
    );
  }

  return (
    <div className="page-container" ref={pageRef}>
      <div className="max-width-container">
        <div className="safe-area-padding" style={{ marginBottom: 'var(--spacing-lg)' }}>
          <h1 style={{ color: 'var(--app-text-color)', fontSize: 'var(--text-xxl)', fontWeight: 600, margin: 0 }}>
            {isEditing ? 'Редактировать тип' : 'Новый тип события'}
          </h1>
          {/* Someone else's type: the form below is there to read, not to fill in. Without this the person
              filled in a whole form of a type they don't own and only found out on «Сохранить». */}
          {isEditing && !canEdit && existing && (
            <div className="card-soft" style={{ padding: 'var(--spacing-md)', marginTop: 'var(--spacing-md)' }}>
              <div style={{ fontSize: 'var(--text-sm)', color: 'var(--app-text-secondary)' }}>
                {existing.is_builtin
                  ? 'Встроенный тип, меняет его администратор'
                  : `Этот тип создал(а) ${existing.created_by}, менять его может только он`}
              </div>
              {/* What an admin's change to a built-in type means: it is the same type for every account in
                  Petzy, not this person's copy of it. */}
              {existing.is_builtin && canEdit && (
                <div style={{ fontSize: 'var(--text-sm)', color: 'var(--app-text-secondary)', marginTop: 'var(--spacing-2xs)' }}>
                  Изменение увидят все, кто пользуется Petzy
                </div>
              )}
            </div>
          )}
        </div>

        {/* A fieldset is what makes the whole form read-only: one property instead of a `disabled` on every
            input, switch and picker, and it survives the next field added to the form. */}
        <fieldset disabled={!canEdit} style={{ border: 'none', margin: 0, padding: 0, minWidth: 0 }}>
        <div className="safe-area-padding">
          <h2 className="section-header" style={{ marginBottom: 'var(--spacing-sm)' }}>Название</h2>
          <Input
            className="input-row"
            value={label}
            onChange={(v) => { setLabel(v); setLabelError(null); }}
            placeholder="Например, Массаж"
            clearable
            maxLength={100}
            aria-invalid={!!labelError}
          />
          {/* The name is shared by everybody who has this type, so the limit is said rather than met silently. */}
          {fieldNote({ error: labelError ?? undefined, value: label, max: 100 })}
        </div>

        <div className="safe-area-padding" style={{ marginTop: 'var(--spacing-lg)' }}>
          <h2 className="section-header" style={{ marginBottom: 'var(--spacing-sm)' }}>Иконка</h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(44px, 1fr))', gap: '8px' }}>
            {ICON_OPTIONS.map(({ key: iconKey, Icon, label: iconLabel }) => (
              <button
                key={iconKey}
                type="button"
                onClick={() => setIcon(iconKey)}
                aria-label={iconLabel}
                aria-pressed={icon === iconKey}
                title={iconLabel}
                style={{
                  width: 44, height: 44, borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: icon === iconKey ? (pastelColorMap[color] ?? 'var(--tile-blue)') : 'var(--app-card-background)',
                  border: icon === iconKey ? '2px solid var(--app-primary-color)' : '1px solid var(--app-border-color)',
                  color: icon === iconKey ? 'var(--app-text-on-tile)' : 'var(--app-text-secondary)',
                  cursor: 'pointer',
                }}
              >
                <Icon size={20} strokeWidth={2} />
              </button>
            ))}
          </div>
        </div>

        <div className="safe-area-padding" style={{ marginTop: 'var(--spacing-lg)' }}>
          <h2 className="section-header" style={{ marginBottom: 'var(--spacing-sm)' }}>Цвет</h2>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--spacing-md)' }}>
            {Object.values(TILE_COLORS).map((c) => (
              <button
                key={c}
                type="button"
                className="touch-target"
                onClick={() => setColor(c)}
                aria-label={TILE_COLOR_LABELS[c]}
                aria-pressed={color === c}
                style={{
                  width: 32, height: 32, borderRadius: '50%',
                  background: pastelColorMap[c] ?? c,
                  border: color === c ? '3px solid var(--app-primary-color)' : '1px solid var(--app-border-color)',
                  cursor: 'pointer',
                }}
              />
            ))}
          </div>
        </div>

        <div className="safe-area-padding" style={{ marginTop: 'var(--spacing-lg)' }}>
          <h2 className="section-header" style={{ marginBottom: 'var(--spacing-sm)' }}>
            Поля {fields.length > 0 && `(${fields.length})`}
          </h2>
          {/* No room under this text: the button below carries it (12px), so the pair is one gap and
              not two summed (8px here plus 12px there made 20px, off the spacing ladder). */}
          <p style={{ margin: 0, fontSize: 'var(--text-sm)', color: 'var(--app-text-secondary)' }}>
            Дата, время и комментарий добавляются автоматически. Здесь только то, что нужно именно этому типу
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
            {fields.map((field, index) => (
              <div key={field.key} className="card-soft" style={{ padding: 'var(--spacing-lg)' }}>
                <div style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  marginBottom: '12px',
                }}>
                  <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--app-text-secondary)' }}>
                    Поле {index + 1}
                  </span>
                  <button
                    type="button"
                    aria-label="Удалить поле"
                    className="touch-target"
                    onClick={() => removeField(field.key)}
                    style={{ background: 'transparent', border: 'none', color: 'var(--app-danger-text)', cursor: 'pointer', padding: 4, display: 'flex' }}
                  >
                    <Trash2 size={17} strokeWidth={2} />
                  </button>
                </div>

                <FieldLabel>Подпись поля</FieldLabel>
                <Input
                  className="input-row"
                  value={field.label}
                  onChange={(v) => updateField(field.key, { label: v })}
                  placeholder="Например, Длительность"
                  clearable
                  maxLength={100}
                  aria-invalid={!!fieldErrors[field.key]?.label}
                />
                <FieldError message={fieldErrors[field.key]?.label} />
                {fieldNote({ value: field.label, max: 100 })}

                <FieldLabel>Тип поля</FieldLabel>
                <Selector
                  options={FIELD_TYPE_OPTIONS}
                  value={[field.type]}
                  onChange={(v) => updateField(field.key, { type: (v[0] as FieldType) ?? 'text' })}
                  columns={2}
                  style={{ marginBottom: '12px', '--gap': '6px' } as React.CSSProperties}
                />

                {field.type === 'select' && (
                  <>
                    <FieldLabel>Варианты, по одному на строку</FieldLabel>
                    <TextArea
                      value={field.optionsText}
                      onChange={(v) => updateField(field.key, { optionsText: v })}
                      placeholder={'Мало\nСредне\nМного'}
                      rows={3}
                      aria-invalid={!!fieldErrors[field.key]?.options}
                    />
                    <FieldError message={fieldErrors[field.key]?.options} />
                  </>
                )}

                {/* What the record form will accept for this number: shown rather than edited, and kept by the
                    save, so relabelling a field doesn't quietly widen what can be written into it. */}
                {field.type === 'number' &&
                  (() => {
                    const stored = storedFields.find((s) => s.name === resolvedNames[field.key]);
                    const note = stored ? fieldNote({ hint: boundsText(stored) }) : undefined;
                    return note ? <div style={{ marginBottom: '12px' }}>{note}</div> : null;
                  })()}

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Switch
                    aria-label={`Обязательное, поле ${index + 1}`}
                    checked={field.required}
                    onChange={(checked) => updateField(field.key, { required: checked })}
                  />
                  <span style={{ fontSize: 'var(--text-sm)', color: 'var(--app-text-primary)' }}>Обязательное</span>
                </div>
              </div>
            ))}
          </div>

          <Button
            block
            fill="outline"
            color="primary"
            onClick={addField}
            style={{ marginTop: 'var(--spacing-md)' }}
          >
            <Plus size={16} strokeWidth={2.4} style={{ verticalAlign: 'middle', marginRight: 'var(--spacing-sm)' }} />
            Добавить поле
          </Button>
        </div>

        <div className="safe-area-padding" style={{ marginTop: 'var(--spacing-lg)' }}>
          <h2 className="section-header" style={{ marginBottom: 'var(--spacing-sm)' }}>График в истории</h2>
          <Selector
            options={[
              { label: 'Считать количество за день', value: 'count' },
              { label: 'Показывать значение числового поля', value: 'value' },
            ]}
            value={[chartKind]}
            onChange={(v) => setChartKind((v[0] as 'count' | 'value') ?? 'count')}
            columns={1}
            style={{ marginBottom: 'var(--spacing-md)' }}
          />
          {chartKind === 'value' && (
            <>
              {numberFields.length === 0 ? (
                <p style={{ fontSize: 'var(--text-sm)', color: 'var(--app-text-secondary)' }}>
                  Добавьте числовое поле выше, чтобы построить по нему график
                </p>
              ) : (
                <>
                  <Selector
                    options={numberFields.map((f) => ({ label: f.label || '(без подписи)', value: f.resolvedName }))}
                    value={chartValueName ? [chartValueName] : []}
                    onChange={(v) => {
                      setChartValueName((v[0] as string) ?? '');
                      setChartFieldLost(false);
                      setChartError(null);
                    }}
                    columns={1}
                    aria-label="Поле для графика"
                  />
                  {/* Deleting or retyping the field the chart was on empties it: said here, so the history's graph
                      is not found plotting a number nobody chose. */}
                  {chartFieldLost && !chartError && fieldNote({ hint: 'Поле для графика ушло, выберите другое' })}
                </>
              )}
              <FieldError message={chartError ?? undefined} />
              <Input
                className="input-row"
                value={chartValueLabel}
                onChange={setChartValueLabel}
                placeholder="Подпись оси (например, Вес (кг))"
                maxLength={50}
              />
              {fieldNote({ value: chartValueLabel, max: 50 })}
            </>
          )}
        </div>

        </fieldset>

        <div className="safe-area-padding" style={{
          paddingTop: 'var(--spacing-xl)',
          paddingBottom: 'var(--spacing-xl)',
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--spacing-md)',
        }}>
          {/* No «Сохранить» on a type that isn't this person's: a button that always refuses is worse than
              no button, and the notice at the top already says who does change it. */}
          {canEdit ? (
            <Button
              block
              color="primary"
              size="large"
              loading={isSaving}
              onClick={handleSave}
            >
              {isEditing ? 'Сохранить' : 'Создать'}
            </Button>
          ) : (
            <Button block size="large" onClick={() => navigate('/event-types')}>
              К типам событий
            </Button>
          )}
          {canEdit && (
            <Button block size="large" onClick={() => goBack(navigate, '/event-types')}>
              Отмена
            </Button>
          )}
        </div>
      </div>
      {leaveDialog}
    </div>
  );
}
