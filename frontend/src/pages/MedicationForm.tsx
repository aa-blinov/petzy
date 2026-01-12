import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Button, Form, Input, Switch, Toast, Selector, Picker, Popup, List } from 'antd-mobile';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm, Controller, useFieldArray } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { DeleteOutline, SearchOutline } from 'antd-mobile-icons';
import { medicationsService, type MedicationCreate, COMMON_MEDICATIONS } from '../services/medications.service';
import { usePet } from '../hooks/usePet';
import { LoadingSpinner } from '../components/LoadingSpinner';

const medicationSchema = z.object({
    name: z.string().min(1, 'Название обязательно'),
    type: z.string().min(1, 'Тип обязателен'),
    form_factor: z.string().optional(),
    strength: z.string().optional(),
    dose_unit: z.string().optional(),
    default_dose: z.coerce.number().min(0.0001, 'Доза должна быть больше 0'),
    schedule: z.object({
        days: z.array(z.number()).min(1, 'Выберите хотя бы один день'),
        times: z.array(z.string().regex(/^([01]\d|2[0-3]):([0-5]\d)$/, 'Некорректное время')).min(1, 'Добавьте хотя бы одно время'),
    }),
    inventory_enabled: z.boolean(),
    inventory_total: z.preprocess((val) => (val === '' || val === undefined) ? null : val, z.coerce.number().nullable().optional()),
    inventory_current: z.preprocess((val) => (val === '' || val === undefined) ? null : val, z.coerce.number().nullable().optional()),
    inventory_warning_threshold: z.preprocess((val) => (val === '' || val === undefined) ? null : val, z.coerce.number().nullable().optional()),
    is_active: z.boolean(),
    comment: z.string().optional(),
});

type MedicationFormData = z.infer<typeof medicationSchema>;

const DAYS_OF_WEEK = [
    { label: 'Пн', value: 0 },
    { label: 'Вт', value: 1 },
    { label: 'Ср', value: 2 },
    { label: 'Чт', value: 3 },
    { label: 'Пт', value: 4 },
    { label: 'Сб', value: 5 },
    { label: 'Вс', value: 6 },
];

const COMMON_TYPES = ['Таблетка', 'Ингаляция', 'Капли', 'Укол', 'Мазь', 'Сироп', 'Суспензия'];

export function MedicationForm() {
    const { id } = useParams<{ id: string }>();
    const isEditing = !!id;
    const navigate = useNavigate();
    const { selectedPetId } = usePet();
    const queryClient = useQueryClient();
    const [typePickerVisible, setTypePickerVisible] = useState(false);
    const [showCustomType, setShowCustomType] = useState(false);
    const [showCommonMeds, setShowCommonMeds] = useState(false);
    const [activeTimeIndex, setActiveTimeIndex] = useState<number | null>(null);
    const [timePickerVisible, setTimePickerVisible] = useState(false);
    const [unitPickerVisible, setUnitPickerVisible] = useState(false);

    // Time picker columns
    const hours = Array.from({ length: 24 }, (_, i) => ({ label: i.toString().padStart(2, '0'), value: i.toString().padStart(2, '0') }));
    const minutes = Array.from({ length: 60 }, (_, i) => ({ label: i.toString().padStart(2, '0'), value: i.toString().padStart(2, '0') }));

    const { control, handleSubmit, reset, watch, setValue, formState: { errors, isSubmitting } } = useForm<MedicationFormData>({
        resolver: zodResolver(medicationSchema) as any,
        defaultValues: {
            name: '',
            type: '',
            form_factor: 'other',
            strength: '',
            dose_unit: '',
            default_dose: 1,
            schedule: {
                days: [0, 1, 2, 3, 4, 5, 6],
                times: ['08:00'],
            },
            inventory_enabled: false,
            is_active: true,
            comment: '',
        }
    });

    const { fields: timeFields, append: appendTime, remove: removeTime } = useFieldArray({
        control,
        name: 'schedule.times' as never,
    });

    const inventoryEnabled = watch('inventory_enabled');
    const doseUnit = watch('dose_unit') || 'ед.';

    const { data: med, isLoading: isLoadingMed } = useQuery({
        queryKey: ['medication', id],
        queryFn: async () => {
            if (!id || !selectedPetId) return null;
            const meds = await medicationsService.getList(selectedPetId);
            return meds.find(m => m._id === id) || null;
        },
        enabled: isEditing && !!id && !!selectedPetId,
    });

    useEffect(() => {
        if (med) {
            reset({
                name: med.name,
                type: med.type,
                form_factor: med.form_factor || 'other',
                strength: med.strength || '',
                dose_unit: med.dose_unit || med.unit || '',
                default_dose: med.default_dose || 1,
                schedule: {
                    days: med.schedule.days,
                    times: med.schedule.times,
                },
                inventory_enabled: med.inventory_enabled,
                inventory_total: med.inventory_total ?? null,
                inventory_current: med.inventory_current ?? null,
                inventory_warning_threshold: med.inventory_warning_threshold ?? null,
                is_active: med.is_active,
                comment: med.comment || '',
            });
            if (!COMMON_TYPES.includes(med.type)) {
                setShowCustomType(true);
            }
        }
    }, [med, reset]);

    const handleCommonMedSelect = (common: typeof COMMON_MEDICATIONS[0]) => {
        setValue('name', common.name);
        setValue('type', common.type);
        setValue('form_factor', common.form_factor);
        setValue('strength', common.strength);
        setValue('dose_unit', common.dose_unit);
        setValue('default_dose', common.default_dose);
        setShowCommonMeds(false);
        Toast.show({ content: 'Данные заполнены', icon: 'success' });
    };

    const mutation = useMutation({
        mutationFn: async (data: MedicationFormData) => {
            const payload: MedicationCreate = {
                ...data,
                pet_id: selectedPetId!,
                inventory_total: data.inventory_total ?? undefined,
                inventory_current: data.inventory_current ?? undefined,
                inventory_warning_threshold: data.inventory_warning_threshold ?? undefined,
            };
            if (isEditing && id) {
                await medicationsService.update(id, payload);
            } else {
                await medicationsService.create(payload);
            }
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['medications'] });
            Toast.show({
                icon: 'success',
                content: isEditing ? 'Курс обновлен' : 'Курс создан',
                duration: 1500,
                afterClose: () => navigate('/medications')
            });
        },
        onError: (err: any) => {
            Toast.show({ icon: 'fail', content: err?.response?.data?.error || 'Ошибка при сохранении' });
        }
    });

    const onSubmit = (data: MedicationFormData) => {
        if (data.inventory_enabled) {
            if (data.inventory_total !== null && data.inventory_total !== undefined && data.inventory_total <= 0) {
                Toast.show({ icon: 'fail', content: 'Общее количество должно быть больше 0' });
                return;
            }
            if (data.inventory_current !== null && data.inventory_current !== undefined) {
                if (data.inventory_current < 0) {
                    Toast.show({ icon: 'fail', content: 'Текущий остаток не может быть отрицательным' });
                    return;
                }
                if (data.inventory_total !== null && data.inventory_total !== undefined &&
                    data.inventory_current > data.inventory_total) {
                    Toast.show({ icon: 'fail', content: 'Текущий остаток не может превышать общее количество' });
                    return;
                }
            }
        }
        mutation.mutate(data);
    };

    if (isEditing && isLoadingMed) return <LoadingSpinner />;

    return (
        <div className="page-container">
            <div className="max-width-container">
                <div className="safe-area-padding" style={{
                    marginBottom: 'var(--spacing-lg)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    minHeight: '40px',
                }}>
                    <h2 style={{ margin: 0, fontSize: 'var(--text-xxl)', fontWeight: 600 }}>
                        {isEditing ? 'Редактировать курс' : 'Новый курс'}
                    </h2>
                    {!isEditing && (
                        <Button
                            size="small"
                            color="primary"
                            fill="outline"
                            onClick={() => setShowCommonMeds(true)}
                            style={{ borderRadius: 'var(--radius-xl)', fontSize: 'var(--text-xs)' }}
                        >
                            <SearchOutline /> Шаблоны
                        </Button>
                    )}
                </div>

                <div>
                    <Form
                        layout="horizontal"
                        mode="card"
                        onFinish={handleSubmit(onSubmit)}
                        style={{ '--prefix-width': '6em' } as React.CSSProperties}
                    >
                        <Form.Header>Препарат</Form.Header>
                        <Controller
                            name="name"
                            control={control}
                            render={({ field }) => (
                                <Form.Item label="Название" required help={errors.name?.message}>
                                    <Input
                                        value={field.value}
                                        onChange={field.onChange}
                                        placeholder="Напр. Синулокс"
                                        clearable
                                    />
                                </Form.Item>
                            )}
                        />

                        <Controller
                            name="type"
                            control={control}
                            render={({ field }) => (
                                <>
                                    <Form.Item
                                        label="Форма"
                                        required
                                        onClick={() => setTypePickerVisible(true)}
                                        help={errors.type?.message}
                                        style={{ cursor: 'pointer' }}
                                        arrow
                                    >
                                        <Input
                                            readOnly
                                            value={field.value}
                                            placeholder="Выберите тип"
                                            style={{ pointerEvents: 'none' }}
                                        />
                                    </Form.Item>
                                    <Picker
                                        columns={[COMMON_TYPES.map(t => ({ label: t, value: t }))]}
                                        visible={typePickerVisible}
                                        onClose={() => setTypePickerVisible(false)}
                                        value={[showCustomType ? 'Другое...' : field.value]}
                                        onConfirm={(val) => {
                                            const selected = val[0] as string;
                                            if (selected === 'Другое...') {
                                                setShowCustomType(true);
                                                field.onChange('');
                                            } else {
                                                setShowCustomType(false);
                                                field.onChange(selected);

                                                if (selected === 'Таблетка' || selected === 'Капсула') setValue('form_factor', 'tablet');
                                                else if (selected === 'Сироп' || selected === 'Суспензия' || selected === 'Капли') setValue('form_factor', 'liquid');
                                                else if (selected === 'Укол') setValue('form_factor', 'injection');
                                            }
                                            setTypePickerVisible(false);
                                        }}
                                        cancelText="Отмена"
                                        confirmText="Выбрать"
                                    />
                                </>
                            )}
                        />

                        <Controller
                            name="strength"
                            control={control}
                            render={({ field }) => (
                                <Form.Item label="Дозировка">
                                    <Input
                                        value={field.value}
                                        onChange={field.onChange}
                                        placeholder="Напр. 50 мг или 0.5 мг/мл"
                                    />
                                </Form.Item>
                            )}
                        />

                        <Form.Header>Схема приема</Form.Header>
                        <Controller
                            name="default_dose"
                            control={control}
                            render={({ field }) => (
                                <Form.Item label="Разовая" required help={errors.default_dose?.message}>
                                    <div style={{ display: 'flex', gap: 'var(--spacing-md)', alignItems: 'center' }}>
                                        <Input
                                            value={field.value?.toString()}
                                            onChange={val => {
                                                if (val === '' || /^\d*\.?\d*$/.test(val)) {
                                                    field.onChange(val);
                                                }
                                            }}
                                            type="text"
                                            inputMode="decimal"
                                            style={{ width: '80px' }}
                                        />

                                        <div style={{ width: '1px', height: '24px', backgroundColor: 'var(--app-border-color)', margin: `0 var(--spacing-xs)` }} />

                                        <div style={{ width: '80px' }}>
                                            <Controller
                                                name="dose_unit"
                                                control={control}
                                                render={({ field: unitField }) => (
                                                    <div onClick={() => setUnitPickerVisible(true)}>
                                                        <Input
                                                            value={unitField.value}
                                                            readOnly
                                                            placeholder="ед."
                                                            style={{
                                                                '--text-align': 'center',
                                                                color: 'var(--app-primary-color)',
                                                                cursor: 'pointer'
                                                            }}
                                                        />
                                                    </div>
                                                )}
                                            />
                                        </div>
                                        <Picker
                                            columns={[['таб', 'мл', 'мг', 'капс', 'шт', 'ед'].map(u => ({ label: u, value: u }))]}
                                            visible={unitPickerVisible}
                                            onClose={() => setUnitPickerVisible(false)}
                                            value={[watch('dose_unit') || 'ед']}
                                            onConfirm={v => {
                                                if (v[0]) setValue('dose_unit', v[0] as string);
                                            }}
                                            cancelText="Отмена"
                                            confirmText="Выбрать"
                                        />
                                    </div>
                                </Form.Item>
                            )}
                        />

                        <Form.Item label="Частота" required layout="vertical">
                            <div style={{ marginBottom: 'var(--spacing-lg)' }}>
                                <Controller
                                    name="schedule.days"
                                    control={control}
                                    render={({ field }) => (
                                        <Selector
                                            columns={7}
                                            options={DAYS_OF_WEEK}
                                            multiple
                                            value={field.value}
                                            onChange={(val) => field.onChange(val)}
                                            style={{
                                                '--border-radius': 'var(--radius-sm)',
                                                '--padding': 'var(--spacing-xs) 0',
                                                '--gap': 'var(--spacing-xs)'
                                            }}
                                        />
                                    )}
                                />
                            </div>

                            {timeFields.map((timeField: any, index) => (
                                <div key={timeField.id} style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
                                    <div
                                        style={{ flex: 1, cursor: 'pointer' }}
                                        onClick={() => {
                                            setActiveTimeIndex(index);
                                            setTimePickerVisible(true);
                                        }}
                                    >
                                        <Controller
                                            name={`schedule.times.${index}` as any}
                                            control={control}
                                            render={({ field: tField }) => (
                                                <Input
                                                    value={tField.value}
                                                    readOnly
                                                    placeholder="Выберите время"
                                                    style={{
                                                        width: '100%',
                                                        padding: '10px 12px', /* Roughly var(--spacing-md) */
                                                        borderRadius: 'var(--radius-sm)',
                                                        backgroundColor: 'var(--app-page-background)',
                                                        pointerEvents: 'none',
                                                        fontSize: 'var(--text-md)',
                                                        fontWeight: 500,
                                                        '--text-align': 'center'
                                                    }}
                                                />
                                            )}
                                        />
                                    </div>
                                    {timeFields.length > 1 && (
                                        <Button
                                            size="small"
                                            color="danger"
                                            fill="none"
                                            onClick={() => removeTime(index)}
                                        >
                                            <DeleteOutline fontSize={20} />
                                        </Button>
                                    )}
                                </div>
                            ))}
                            <Button
                                size="mini"
                                fill="outline"
                                color="primary"
                                onClick={() => appendTime('08:00')}
                                style={{ borderRadius: 'var(--radius-md)', marginTop: 'var(--spacing-xs)' }}
                            >
                                + Время
                            </Button>

                            <Picker
                                columns={[hours, minutes]}
                                visible={timePickerVisible}
                                onClose={() => {
                                    setTimePickerVisible(false);
                                    setActiveTimeIndex(null);
                                }}
                                value={activeTimeIndex !== null ? (watch(`schedule.times.${activeTimeIndex}`) || '08:00').split(':') : ['08', '00']}
                                onConfirm={(val) => {
                                    if (activeTimeIndex !== null) {
                                        const newTime = `${val[0]}:${val[1]}`;
                                        setValue(`schedule.times.${activeTimeIndex}`, newTime);
                                    }
                                    setTimePickerVisible(false);
                                    setActiveTimeIndex(null);
                                }}
                                cancelText="Отмена"
                                confirmText="Выбрать"
                                title="Выберите время"
                            />
                        </Form.Item>

                        <Form.Header>Учет остатков</Form.Header>
                        <Controller
                            name="inventory_enabled"
                            control={control}
                            render={({ field }) => (
                                <Form.Item
                                    label="Включить"
                                    extra={<Switch checked={field.value} onChange={field.onChange} />}
                                    description={field.value ? `Будем списывать по ${watch('default_dose') || 1} ${doseUnit} за прием` : undefined}
                                />
                            )}
                        />

                        {inventoryEnabled && (
                            <>
                                <Controller
                                    name="inventory_current"
                                    control={control}
                                    render={({ field }) => (
                                        <Form.Item label={`Остаток (${doseUnit})`}>
                                            <Input
                                                value={field.value !== null && field.value !== undefined ? String(field.value) : ''}
                                                onChange={val => {
                                                    if (val === '' || /^\d*\.?\d*$/.test(val)) {
                                                        field.onChange(val === '' ? null : val);
                                                    }
                                                }}
                                                type="text"
                                                inputMode="decimal"
                                                placeholder="0"
                                            />
                                        </Form.Item>
                                    )}
                                />
                                <Controller
                                    name="inventory_warning_threshold"
                                    control={control}
                                    render={({ field }) => (
                                        <Form.Item label="Мин. остаток">
                                            <Input
                                                value={field.value !== null && field.value !== undefined ? String(field.value) : ''}
                                                onChange={val => {
                                                    if (val === '' || /^\d*\.?\d*$/.test(val)) {
                                                        field.onChange(val === '' ? null : val);
                                                    }
                                                }}
                                                type="text"
                                                inputMode="decimal"
                                                placeholder="0"
                                            />
                                        </Form.Item>
                                    )}
                                />
                            </>
                        )}

                        <Form.Header />
                        <Controller
                            name="is_active"
                            control={control}
                            render={({ field }) => (
                                <Form.Item
                                    label="Активный курс"
                                    extra={<Switch checked={field.value} onChange={field.onChange} />}
                                />
                            )}
                        />
                        <Controller
                            name="comment"
                            control={control}
                            render={({ field }) => (
                                <Form.Item label="Комментарий">
                                    <Input
                                        value={field.value}
                                        onChange={field.onChange}
                                        placeholder="Напр. от кашля"
                                        style={{ '--text-align': 'left' }}
                                    />
                                </Form.Item>
                            )}
                        />
                    </Form>

                    <div style={{
                        marginTop: 'var(--spacing-xl)',
                        paddingBottom: 'var(--spacing-xl)',
                        marginLeft: 'var(--spacing-md)',
                        marginRight: 'var(--spacing-md)'
                    }}>
                        <Button
                            block
                            color="primary"
                            size="large"
                            onClick={() => handleSubmit(onSubmit)()}
                            loading={mutation.isPending || isSubmitting}
                            style={{ borderRadius: 'var(--radius-md)', fontWeight: 600, marginBottom: 'var(--spacing-md)' }}
                        >
                            {isEditing ? 'Сохранить' : 'Создать'}
                        </Button>
                        <Button
                            block
                            size="large"
                            onClick={() => navigate('/medications')}
                            style={{ borderRadius: 'var(--radius-md)', fontWeight: 500 }}
                        >
                            Отмена
                        </Button>
                    </div>
                </div>
            </div>

            <Popup
                visible={showCommonMeds}
                onMaskClick={() => setShowCommonMeds(false)}
                bodyStyle={{ height: '60vh', borderTopLeftRadius: 'var(--radius-md)', borderTopRightRadius: 'var(--radius-md)' }}
            >
                <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                    <div style={{ padding: 'var(--spacing-lg)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--app-border-color)' }}>
                        <span style={{ fontSize: 'var(--text-lg)', fontWeight: 600 }}>Популярные препараты</span>
                        <Button fill="none" color="primary" onClick={() => setShowCommonMeds(false)}>Закрыть</Button>
                    </div>
                    <div style={{ overflowY: 'auto', flex: 1 }}>
                        <List>
                            {COMMON_MEDICATIONS.map((med, idx) => (
                                <List.Item
                                    key={idx}
                                    onClick={() => handleCommonMedSelect(med)}
                                    arrow
                                >
                                    <div style={{ fontWeight: 500 }}>{med.name}</div>
                                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--app-text-tertiary)' }}>
                                        {med.type}, {med.strength} ({med.default_dose} {med.dose_unit})
                                    </div>
                                </List.Item>
                            ))}
                        </List>
                    </div>
                </div>
            </Popup>
        </div>
    );
}
