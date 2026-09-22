/**
 * Create/edit an event type — the "factory" itself.
 *
 * Kept as plain component state rather than react-hook-form: the field
 * list is a dynamic array with its own per-row shape (options text only
 * shown for `select`), which react-hook-form's typed API doesn't make
 * meaningfully simpler here.
 */

import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Button, Input, Switch, Selector, TextArea } from 'antd-mobile';
import { Trash2, Plus } from 'lucide-react';

import { showToast } from '../utils/toast';
import { useEventTypes, useInvalidateEventTypes } from '../hooks/useEventTypes';
import { eventTypesService, type EventTypeField } from '../services/eventTypes.service';
import { TILE_COLORS, pastelColorMap, type TileColor } from '../utils/constants';
import { ICON_OPTIONS } from '../utils/iconRegistry';
import { slugifyFieldName } from '../utils/slugify';
import { LoadingSpinner } from '../components/LoadingSpinner';

type FieldType = EventTypeField['type'];

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
    <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--app-text-tertiary)', marginBottom: '4px' }}>
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
  const { eventTypesByKey, isLoading: eventTypesLoading } = useEventTypes();
  const invalidate = useInvalidateEventTypes();
  const existing = key ? eventTypesByKey[key] : undefined;

  const [label, setLabel] = useState('');
  const [icon, setIcon] = useState('paw');
  const [color, setColor] = useState<TileColor>('blue');
  const [fields, setFields] = useState<FieldDraft[]>([]);
  const [chartKind, setChartKind] = useState<'count' | 'value'>('count');
  const [chartValueName, setChartValueName] = useState('');
  const [chartValueLabel, setChartValueLabel] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [loadedExisting, setLoadedExisting] = useState(!isEditing);

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

  // If the field backing the chart gets deleted or retyped, its resolved
  // name disappears from numberFields — the Selector below would then show
  // nothing selected while `chartValueName` silently still held the old
  // (now-dangling) name, which handleSave would happily save anyway. Keep
  // the state itself consistent instead of just hiding the mismatch.
  useEffect(() => {
    if (chartValueName && !numberFields.some((f) => f.resolvedName === chartValueName)) {
      setChartValueName(numberFields[0]?.resolvedName ?? '');
    }
  }, [numberFields, chartValueName]);

  const addField = () => {
    setFields((prev) => [
      ...prev,
      { key: newDraftKey(), name: '', label: '', type: 'text', required: false, optionsText: '' },
    ]);
  };

  const updateField = (key: string, patch: Partial<FieldDraft>) => {
    setFields((prev) => prev.map((f) => (f.key === key ? { ...f, ...patch } : f)));
  };

  const removeField = (key: string) => {
    setFields((prev) => prev.filter((f) => f.key !== key));
  };

  const handleSave = async () => {
    if (!label.trim()) {
      showToast.failure('Укажите название типа');
      return;
    }
    if (fields.some((f) => !f.label.trim())) {
      showToast.failure('У каждого поля должна быть подпись');
      return;
    }
    if (fields.some((f) => f.type === 'select' && !f.optionsText.trim())) {
      showToast.failure('Для поля «Выбор из списка» укажите хотя бы один вариант');
      return;
    }
    {
      // Names are already de-duplicated by slugifyFieldName, so the
      // backend's own uniqueness check never catches this — but two
      // fields sharing a label are indistinguishable everywhere they're
      // actually shown (the form, history), so it's checked here instead.
      const seenLabels = new Set<string>();
      const hasDuplicateLabel = fields.some((f) => {
        const normalized = f.label.trim().toLowerCase();
        if (!normalized) return false;
        if (seenLabels.has(normalized)) return true;
        seenLabels.add(normalized);
        return false;
      });
      if (hasDuplicateLabel) {
        showToast.failure('Подписи полей не должны повторяться');
        return;
      }
    }
    if (chartKind === 'value' && numberFields.length === 0) {
      showToast.failure('Для графика по значению нужно хотя бы одно числовое поле');
      return;
    }

    const resolvedFields: EventTypeField[] = fields.map((f) => {
      const options = f.type === 'select'
        ? f.optionsText.split('\n').map((line) => line.trim()).filter(Boolean).map((text) => ({ value: text, text }))
        : undefined;
      return { name: resolvedNames[f.key], label: f.label.trim(), type: f.type, required: f.required, options };
    });

    // Re-validate against the fields actually being saved rather than
    // trusting `chartValueName` outright — belt-and-suspenders alongside
    // the effect above that keeps it in sync as fields change.
    const chartValueFieldResolved = chartKind === 'value'
      ? (resolvedFields.some((f) => f.type === 'number' && f.name === chartValueName)
          ? chartValueName
          : resolvedFields.find((f) => f.type === 'number')?.name)
      : undefined;

    const payload = {
      label: label.trim(),
      icon,
      color,
      fields: resolvedFields,
      chart: chartKind === 'value'
        ? { kind: 'value' as const, value_field: chartValueFieldResolved, value_label: chartValueLabel.trim() || 'Значение' }
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
      navigate('/event-types');
    } catch (error: any) {
      const message = error.response?.data?.error || 'Не удалось сохранить тип события';
      showToast.failure(message);
    } finally {
      setIsSaving(false);
    }
  };

  if (isEditing && (eventTypesLoading || !loadedExisting)) {
    return <LoadingSpinner />;
  }

  if (isEditing && !existing) {
    return (
      <div style={{ padding: '20px', textAlign: 'center' }}>
        <p>Тип события не найден</p>
        <Button onClick={() => navigate('/event-types')}>Назад</Button>
      </div>
    );
  }

  return (
    <div className="page-container">
      <div className="max-width-container">
        <div className="safe-area-padding" style={{ marginBottom: 'var(--spacing-lg)' }}>
          <h2 style={{ color: 'var(--app-text-color)', fontSize: 'var(--text-xxl)', fontWeight: 600, margin: 0 }}>
            {isEditing ? 'Редактировать тип' : 'Новый тип события'}
          </h2>
        </div>

        <div className="safe-area-padding">
          <h3 className="section-header" style={{ marginBottom: 'var(--spacing-sm)' }}>Название</h3>
          <Input value={label} onChange={setLabel} placeholder="Например, Игра" clearable />
        </div>

        <div className="safe-area-padding" style={{ marginTop: 'var(--spacing-lg)' }}>
          <h3 className="section-header" style={{ marginBottom: 'var(--spacing-sm)' }}>Иконка</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(44px, 1fr))', gap: '8px' }}>
            {ICON_OPTIONS.map(({ key: iconKey, Icon }) => (
              <button
                key={iconKey}
                type="button"
                onClick={() => setIcon(iconKey)}
                aria-label={iconKey}
                aria-pressed={icon === iconKey}
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
          <h3 className="section-header" style={{ marginBottom: 'var(--spacing-sm)' }}>Цвет</h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
            {Object.values(TILE_COLORS).map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => setColor(c)}
                aria-label={c}
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
          <h3 className="section-header" style={{ marginBottom: 'var(--spacing-sm)' }}>
            Поля {fields.length > 0 && `(${fields.length})`}
          </h3>
          <p style={{ margin: '0 0 var(--spacing-sm) 0', fontSize: '13px', color: 'var(--app-text-secondary)' }}>
            Дата, время и комментарий добавляются автоматически — здесь только то, что специфично для этого типа.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {fields.map((field, index) => (
              <div key={field.key} className="card-soft" style={{ padding: '14px' }}>
                <div style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  marginBottom: '12px',
                }}>
                  <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--app-text-secondary)' }}>
                    Поле {index + 1}
                  </span>
                  <button
                    type="button"
                    aria-label="Удалить поле"
                    onClick={() => removeField(field.key)}
                    style={{ background: 'transparent', border: 'none', color: 'var(--app-danger-color)', cursor: 'pointer', padding: 4, display: 'flex' }}
                  >
                    <Trash2 size={17} strokeWidth={2} />
                  </button>
                </div>

                <FieldLabel>Подпись поля</FieldLabel>
                <Input
                  value={field.label}
                  onChange={(v) => updateField(field.key, { label: v })}
                  placeholder="Например, Длительность"
                  clearable
                  style={{ marginBottom: '12px' }}
                />

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
                    <FieldLabel>Варианты — по одному на строку</FieldLabel>
                    <TextArea
                      value={field.optionsText}
                      onChange={(v) => updateField(field.key, { optionsText: v })}
                      placeholder={'Мало\nСредне\nМного'}
                      rows={3}
                      style={{ marginBottom: '12px' }}
                    />
                  </>
                )}

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Switch
                    checked={field.required}
                    onChange={(checked) => updateField(field.key, { required: checked })}
                  />
                  <span style={{ fontSize: '14px', color: 'var(--app-text-primary)' }}>Обязательное</span>
                </div>
              </div>
            ))}
          </div>

          <Button
            block
            fill="outline"
            onClick={addField}
            style={{ marginTop: '10px', borderRadius: 'var(--radius-md)' }}
          >
            <Plus size={16} strokeWidth={2.4} style={{ verticalAlign: 'middle', marginRight: 6 }} />
            Добавить поле
          </Button>
        </div>

        <div className="safe-area-padding" style={{ marginTop: 'var(--spacing-lg)' }}>
          <h3 className="section-header" style={{ marginBottom: 'var(--spacing-sm)' }}>График в истории</h3>
          <Selector
            options={[
              { label: 'Считать количество за день', value: 'count' },
              { label: 'Показывать значение числового поля', value: 'value' },
            ]}
            value={[chartKind]}
            onChange={(v) => setChartKind((v[0] as 'count' | 'value') ?? 'count')}
            columns={1}
            style={{ marginBottom: '10px' }}
          />
          {chartKind === 'value' && (
            <>
              {numberFields.length === 0 ? (
                <p style={{ fontSize: '13px', color: 'var(--app-text-secondary)' }}>
                  Добавьте числовое поле выше, чтобы построить по нему график.
                </p>
              ) : (
                <Selector
                  options={numberFields.map((f) => ({ label: f.label || '(без подписи)', value: f.resolvedName }))}
                  value={chartValueName ? [chartValueName] : []}
                  onChange={(v) => setChartValueName((v[0] as string) ?? '')}
                  columns={1}
                  style={{ marginBottom: '8px' }}
                />
              )}
              <Input
                value={chartValueLabel}
                onChange={setChartValueLabel}
                placeholder="Подпись оси (например, Вес (кг))"
              />
            </>
          )}
        </div>

        <div className="safe-area-padding" style={{
          paddingTop: 'var(--spacing-xl)',
          paddingBottom: 'var(--spacing-xl)',
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--spacing-md)',
        }}>
          <Button
            block
            color="primary"
            size="large"
            loading={isSaving}
            onClick={handleSave}
            style={{ borderRadius: 'var(--radius-md)', fontWeight: 600 }}
          >
            {isEditing ? 'Сохранить' : 'Создать'}
          </Button>
          <Button block size="large" onClick={() => navigate('/event-types')} style={{ borderRadius: 'var(--radius-md)', fontWeight: 500 }}>
            Отмена
          </Button>
        </div>
      </div>
    </div>
  );
}
