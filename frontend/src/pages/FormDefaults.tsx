import { useState, useEffect, useCallback, useRef } from 'react';
import { showToast } from '../utils/toast';
import { useNavigate } from 'react-router-dom';
import { Button, Form, Picker } from 'antd-mobile';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { DEFAULT_FORM_SETTINGS, cacheFormSettings, getFormSettings, type FormSettings } from '../utils/formsConfig';
import { formDefaultsService } from '../services/formDefaults.service';

/** Static option lists for each categorical field. Kept here rather than
    in formsConfig so the picker columns read in the same place the
    Form.Item reads them. */
const OPTIONS = {
    asthma_duration: [
        { label: 'Короткий', value: 'Короткий' },
        { label: 'Средний', value: 'Средний' },
        { label: 'Длинный', value: 'Длинный' },
    ],
    asthma_inhalation: [
        { label: 'Нет', value: 'false' },
        { label: 'Да', value: 'true' },
    ],
    defecation_stool_type: [
        { label: 'Обычный', value: 'Обычный' },
        { label: 'Твердый', value: 'Твердый' },
        { label: 'Жидкий', value: 'Жидкий' },
    ],
    defecation_color: [
        { label: 'Коричневый', value: 'Коричневый' },
        { label: 'Темно-коричневый', value: 'Темно-коричневый' },
        { label: 'Светло-коричневый', value: 'Светло-коричневый' },
        { label: 'Другой', value: 'Другой' },
    ],
    eye_drops_type: [
        { label: 'Обычные', value: 'Обычные' },
        { label: 'Гелевые', value: 'Гелевые' },
    ],
    tooth_brushing_type: [
        { label: 'Щетка', value: 'Щетка' },
        { label: 'Марля', value: 'Марля' },
        { label: 'Игрушка', value: 'Игрушка' },
    ],
    ear_cleaning_type: [
        { label: 'Салфетка/Марля', value: 'Салфетка/Марля' },
        { label: 'Капли', value: 'Капли' },
    ],
} as const;

type PickerKey = keyof typeof OPTIONS;

interface PickerRowProps {
    label: string;
    pickerKey: PickerKey;
    value: string;
    formType: keyof FormSettings;
    field: string;
    placeholder?: string;
    visiblePicker: PickerKey | null;
    onOpenPicker: (key: PickerKey) => void;
    onClosePicker: () => void;
    onUpdate: (formType: keyof FormSettings, field: string, value: string) => void;
}

/** Renders a categorical field — same look as PetForm's species /
    gender / sterilisation pickers (chevron + selected-or-placeholder).
    Defined at module scope (not inside FormDefaults) so it's a stable
    component across renders rather than a fresh one every time — the
    picker-open state and update callback come in as props instead of
    being captured from an enclosing closure. */
function PickerRow({
    label,
    pickerKey,
    value,
    formType,
    field,
    placeholder = 'Не выбрано',
    visiblePicker,
    onOpenPicker,
    onClosePicker,
    onUpdate,
}: PickerRowProps) {
    const selected = OPTIONS[pickerKey].find(o => o.value === value);
    const display = selected?.label || placeholder;
    return (
        <Form.Item
            label={label}
            clickable
            arrow
            onClick={() => onOpenPicker(pickerKey)}
        >
            <span style={{
                color: selected ? 'var(--app-text-primary)' : 'var(--app-text-tertiary)',
            }}>
                {display}
            </span>
            <Picker
                columns={[[...OPTIONS[pickerKey]]]}
                visible={visiblePicker === pickerKey}
                value={[value]}
                onClose={onClosePicker}
                onConfirm={(val) => {
                    onUpdate(formType, field, val[0] as string);
                    onClosePicker();
                }}
                cancelText="Отмена"
                confirmText="Выбрать"
            />
        </Form.Item>
    );
}

export function FormDefaults() {
    const navigate = useNavigate();
    const mountedRef = useRef(true);
    const [formSettings, setFormSettings] = useState<FormSettings>(() => getFormSettings());
    const [visiblePicker, setVisiblePicker] = useState<PickerKey | null>(null);
    const [saving, setSaving] = useState(false);
    const edited = useRef(false);
    const queryClient = useQueryClient();

    // The account's copy: set on another device, it replaces this one's
    // cached copy unless something was already changed here.
    const { data: serverSettings } = useQuery({
        queryKey: ['form-defaults'],
        queryFn: () => formDefaultsService.get(),
    });
    useEffect(() => {
        if (serverSettings && Object.keys(serverSettings).length > 0 && !edited.current) {
            setFormSettings(serverSettings);
            cacheFormSettings(serverSettings);
        }
    }, [serverSettings]);

    useEffect(() => {
        mountedRef.current = true;
        return () => {
            mountedRef.current = false;
        };
    }, []);

    const persist = useCallback(async (settings: FormSettings) => {
        await formDefaultsService.save(settings);
        cacheFormSettings(settings);
        queryClient.setQueryData(['form-defaults'], settings);
    }, [queryClient]);

    const handleSave = useCallback(async () => {
        if (saving) return;
        setSaving(true);
        try {
            await persist(formSettings);
            showToast.success('Настройки сохранены');
            setTimeout(() => {
                if (mountedRef.current) {
                    navigate('/settings');
                }
            }, 1000);
        } catch (err) {
            showToast.failure('Не удалось сохранить настройки');
            console.error('Error saving settings:', err);
        } finally {
            if (mountedRef.current) setSaving(false);
        }
    }, [formSettings, navigate, persist, saving]);

    const handleReset = useCallback(async () => {
        const confirmed = window.confirm('Вы уверены, что хотите сбросить все настройки к значениям по умолчанию?');
        if (confirmed) {
            try {
                await persist(DEFAULT_FORM_SETTINGS);
                setFormSettings(DEFAULT_FORM_SETTINGS);
                edited.current = false;
                showToast.success('Настройки сброшены');
            } catch {
                showToast.failure('Не удалось сбросить настройки');
            }
        }
    }, [persist]);

    const updateFormSetting = useCallback((formType: keyof FormSettings, field: string, value: string) => {
        edited.current = true;
        setFormSettings(prev => ({
            ...prev,
            [formType]: {
                ...(prev[formType] || {}),
                [field]: value
            }
        }));
    }, []);



    return (
        <div className="page-container">
            <div className="max-width-container">
                <div className="safe-area-padding" style={{ marginBottom: 'var(--spacing-lg)' }}>
                    <h1 style={{ color: 'var(--app-text-color)', fontSize: 'var(--text-xxl)', fontWeight: 600, margin: 0 }}>Значения по умолчанию</h1>
                </div>

                <Form layout="horizontal" mode="card" style={{ '--prefix-width': '7em' } as React.CSSProperties}>
                    <Form.Header>Приступ астмы</Form.Header>
                    <PickerRow
                        label="Длительность"
                        pickerKey="asthma_duration"
                        value={formSettings.asthma?.duration || 'Короткий'}
                        formType="asthma"
                        field="duration"
                        placeholder="Короткий"
                        visiblePicker={visiblePicker}
                        onOpenPicker={setVisiblePicker}
                        onClosePicker={() => setVisiblePicker(null)}
                        onUpdate={updateFormSetting}
                    />
                    <PickerRow
                        label="Ингаляция"
                        pickerKey="asthma_inhalation"
                        value={formSettings.asthma?.inhalation || 'false'}
                        formType="asthma"
                        field="inhalation"
                        placeholder="Нет"
                        visiblePicker={visiblePicker}
                        onOpenPicker={setVisiblePicker}
                        onClosePicker={() => setVisiblePicker(null)}
                        onUpdate={updateFormSetting}
                    />
                    <Form.Item
                        label="Причина"
                        clickable
                        arrow={false}
                        onClick={() => setVisiblePicker(null)}
                    >
                        {/* Free-text field — no picker needed. The whole row
                            is clickable so the keyboard pops up immediately. */}
                        <input
                            aria-label="Причина"
                            value={formSettings.asthma?.reason || ''}
                            onChange={(e) => updateFormSetting('asthma', 'reason', e.target.value)}
                            placeholder="Пил"
                            style={{
                                border: 'none',
                                background: 'transparent',
                                color: 'var(--app-text-primary)',
                                fontSize: 'var(--text-md)',
                                fontFamily: 'inherit',
                                minWidth: 0,
                                maxWidth: '100%',
                                width: '100%',
                                textAlign: 'left',
                                textOverflow: 'ellipsis',
                                overflow: 'hidden',
                                whiteSpace: 'nowrap',
                            }}
                        />
                    </Form.Item>

                    <Form.Header>Дефекация</Form.Header>
                    <PickerRow
                        label="Тип стула"
                        pickerKey="defecation_stool_type"
                        value={formSettings.defecation?.stool_type || 'Обычный'}
                        formType="defecation"
                        field="stool_type"
                        placeholder="Обычный"
                        visiblePicker={visiblePicker}
                        onOpenPicker={setVisiblePicker}
                        onClosePicker={() => setVisiblePicker(null)}
                        onUpdate={updateFormSetting}
                    />
                    <PickerRow
                        label="Цвет стула"
                        pickerKey="defecation_color"
                        value={formSettings.defecation?.color || 'Коричневый'}
                        formType="defecation"
                        field="color"
                        placeholder="Коричневый"
                        visiblePicker={visiblePicker}
                        onOpenPicker={setVisiblePicker}
                        onClosePicker={() => setVisiblePicker(null)}
                        onUpdate={updateFormSetting}
                    />
                    <Form.Item
                        label="Корм"
                        clickable
                        arrow={false}
                        onClick={() => setVisiblePicker(null)}
                    >
                        <input
                            aria-label="Корм"
                            value={formSettings.defecation?.food || ''}
                            onChange={(e) => updateFormSetting('defecation', 'food', e.target.value)}
                            placeholder="Royal Canin Fibre Response"
                            style={{
                                border: 'none',
                                background: 'transparent',
                                color: 'var(--app-text-primary)',
                                fontSize: 'var(--text-md)',
                                fontFamily: 'inherit',
                                minWidth: 0,
                                maxWidth: '100%',
                                width: '100%',
                                textAlign: 'left',
                                textOverflow: 'ellipsis',
                                overflow: 'hidden',
                                whiteSpace: 'nowrap',
                            }}
                        />
                    </Form.Item>

                    <Form.Header>Вес</Form.Header>
                    <Form.Item
                        label="Корм"
                        clickable
                        arrow={false}
                        onClick={() => setVisiblePicker(null)}
                    >
                        <input
                            aria-label="Корм"
                            value={formSettings.weight?.food || ''}
                            onChange={(e) => updateFormSetting('weight', 'food', e.target.value)}
                            placeholder="Royal Canin Fibre Response"
                            style={{
                                border: 'none',
                                background: 'transparent',
                                color: 'var(--app-text-primary)',
                                fontSize: 'var(--text-md)',
                                fontFamily: 'inherit',
                                minWidth: 0,
                                maxWidth: '100%',
                                width: '100%',
                                textAlign: 'left',
                                textOverflow: 'ellipsis',
                                overflow: 'hidden',
                                whiteSpace: 'nowrap',
                            }}
                        />
                    </Form.Item>

                    <Form.Header>Закапывание глаз</Form.Header>
                    <PickerRow
                        label="Тип капель"
                        pickerKey="eye_drops_type"
                        value={formSettings.eye_drops?.drops_type || 'Обычные'}
                        formType="eye_drops"
                        field="drops_type"
                        placeholder="Обычные"
                        visiblePicker={visiblePicker}
                        onOpenPicker={setVisiblePicker}
                        onClosePicker={() => setVisiblePicker(null)}
                        onUpdate={updateFormSetting}
                    />

                    <Form.Header>Чистка зубов</Form.Header>
                    <PickerRow
                        label="Способ чистки"
                        pickerKey="tooth_brushing_type"
                        value={formSettings.tooth_brushing?.brushing_type || 'Щетка'}
                        formType="tooth_brushing"
                        field="brushing_type"
                        placeholder="Щетка"
                        visiblePicker={visiblePicker}
                        onOpenPicker={setVisiblePicker}
                        onClosePicker={() => setVisiblePicker(null)}
                        onUpdate={updateFormSetting}
                    />

                    <Form.Header>Чистка ушей</Form.Header>
                    <PickerRow
                        label="Способ чистки"
                        pickerKey="ear_cleaning_type"
                        value={formSettings.ear_cleaning?.cleaning_type || 'Салфетка/Марля'}
                        formType="ear_cleaning"
                        field="cleaning_type"
                        placeholder="Салфетка/Марля"
                        visiblePicker={visiblePicker}
                        onOpenPicker={setVisiblePicker}
                        onClosePicker={() => setVisiblePicker(null)}
                        onUpdate={updateFormSetting}
                    />
                </Form>

                {/* Action Buttons */}
                <div style={{ paddingTop: 'var(--spacing-md)', paddingBottom: 'var(--spacing-md)', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <Button block color="primary" size="large" onClick={handleSave} loading={saving}>
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
