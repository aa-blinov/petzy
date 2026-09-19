import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Form, Picker, Toast } from 'antd-mobile';
import { DEFAULT_FORM_SETTINGS, getFormSettings, type FormSettings } from '../utils/formsConfig';

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

export function FormDefaults() {
    const navigate = useNavigate();
    const mountedRef = useRef(true);
    const [formSettings, setFormSettings] = useState<FormSettings>(DEFAULT_FORM_SETTINGS);
    const [visiblePicker, setVisiblePicker] = useState<PickerKey | null>(null);

    useEffect(() => {
        mountedRef.current = true;
        return () => {
            mountedRef.current = false;
        };
    }, []);

    useEffect(() => {
        const settings = getFormSettings();
        setFormSettings(settings);
    }, []);

    const handleSave = useCallback(() => {
        try {
            localStorage.setItem('formDefaults', JSON.stringify(formSettings));
            Toast.show({
                icon: 'success',
                content: 'Настройки успешно сохранены',
                duration: 1000,
            });
            setTimeout(() => {
                if (mountedRef.current) {
                    navigate('/settings');
                }
            }, 1000);
        } catch (err) {
            Toast.show({
                icon: 'fail',
                content: 'Ошибка при сохранении настроек',
            });
            console.error('Error saving settings:', err);
        }
    }, [formSettings, navigate]);

    const handleReset = useCallback(() => {
        const confirmed = window.confirm('Вы уверены, что хотите сбросить все настройки к значениям по умолчанию?');
        if (confirmed) {
            try {
                setFormSettings(DEFAULT_FORM_SETTINGS);
                localStorage.setItem('formDefaults', JSON.stringify(DEFAULT_FORM_SETTINGS));
                Toast.show({
                    icon: 'success',
                    content: 'Настройки сброшены',
                    duration: 1000,
                });
            } catch (err) {
                Toast.show({
                    icon: 'fail',
                    content: 'Ошибка при сбросе настроек',
                });
            }
        }
    }, []);

    const updateFormSetting = useCallback((formType: keyof FormSettings, field: string, value: string) => {
        setFormSettings(prev => ({
            ...prev,
            [formType]: {
                ...(prev[formType] || {}),
                [field]: value
            }
        }));
    }, []);

    /** Renders a categorical field — same look as PetForm's species /
        gender / sterilisation pickers (chevron + selected-or-placeholder). */
    const PickerRow = ({
        label,
        pickerKey,
        value,
        formType,
        field,
        placeholder = 'Не выбрано',
    }: {
        label: string;
        pickerKey: PickerKey;
        value: string;
        formType: keyof FormSettings;
        field: string;
        placeholder?: string;
    }) => {
        const selected = OPTIONS[pickerKey].find(o => o.value === value);
        const display = selected?.label || placeholder;
        return (
            <Form.Item
                label={label}
                clickable
                arrow
                onClick={() => setVisiblePicker(pickerKey)}
            >
                <span style={{
                    color: selected ? 'var(--app-text-primary)' : 'var(--app-text-tertiary)',
                }}>
                    {display}
                </span>
                <Picker
                    columns={[OPTIONS[pickerKey] as any]}
                    visible={visiblePicker === pickerKey}
                    value={[value]}
                    onClose={() => setVisiblePicker(null)}
                    onConfirm={(val) => {
                        updateFormSetting(formType, field, val[0] as string);
                        setVisiblePicker(null);
                    }}
                    cancelText="Отмена"
                    confirmText="Выбрать"
                />
            </Form.Item>
        );
    };

    return (
        <div className="page-container">
            <div className="max-width-container">
                <div className="safe-area-padding" style={{ marginBottom: 'var(--spacing-lg)' }}>
                    <h2 style={{ color: 'var(--app-text-color)', fontSize: 'var(--text-xxl)', fontWeight: 600, margin: 0 }}>Значения по умолчанию</h2>
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
                    />
                    <PickerRow
                        label="Ингаляция"
                        pickerKey="asthma_inhalation"
                        value={formSettings.asthma?.inhalation || 'false'}
                        formType="asthma"
                        field="inhalation"
                        placeholder="Нет"
                    />
                    <Form.Item
                        label="Причина"
                        clickable
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
                                outline: 'none',
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
                    />
                    <PickerRow
                        label="Цвет стула"
                        pickerKey="defecation_color"
                        value={formSettings.defecation?.color || 'Коричневый'}
                        formType="defecation"
                        field="color"
                        placeholder="Коричневый"
                    />
                    <Form.Item
                        label="Корм"
                        clickable
                        onClick={() => setVisiblePicker(null)}
                    >
                        <input
                            aria-label="Корм"
                            value={formSettings.defecation?.food || ''}
                            onChange={(e) => updateFormSetting('defecation', 'food', e.target.value)}
                            placeholder="Royal Canin Fibre Response"
                            style={{
                                border: 'none',
                                outline: 'none',
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
                        onClick={() => setVisiblePicker(null)}
                    >
                        <input
                            aria-label="Корм"
                            value={formSettings.weight?.food || ''}
                            onChange={(e) => updateFormSetting('weight', 'food', e.target.value)}
                            placeholder="Royal Canin Fibre Response"
                            style={{
                                border: 'none',
                                outline: 'none',
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
                    />

                    <Form.Header>Чистка зубов</Form.Header>
                    <PickerRow
                        label="Способ чистки"
                        pickerKey="tooth_brushing_type"
                        value={formSettings.tooth_brushing?.brushing_type || 'Щетка'}
                        formType="tooth_brushing"
                        field="brushing_type"
                        placeholder="Щетка"
                    />

                    <Form.Header>Чистка ушей</Form.Header>
                    <PickerRow
                        label="Способ чистки"
                        pickerKey="ear_cleaning_type"
                        value={formSettings.ear_cleaning?.cleaning_type || 'Салфетка/Марля'}
                        formType="ear_cleaning"
                        field="cleaning_type"
                        placeholder="Салфетка/Марля"
                    />
                </Form>

                {/* Action Buttons */}
                <div style={{ paddingTop: 'var(--spacing-md)', paddingBottom: 'var(--spacing-md)', display: 'flex', flexDirection: 'column', gap: '12px' }}>
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
