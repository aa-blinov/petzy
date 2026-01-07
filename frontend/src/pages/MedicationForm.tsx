import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Button, Form, Input, Switch, Toast, Selector, Picker } from 'antd-mobile';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm, Controller, useFieldArray } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { AddOutline, DeleteOutline } from 'antd-mobile-icons';
import { medicationsService, type MedicationCreate } from '../services/medications.service';
import { usePet } from '../hooks/usePet';
import { LoadingSpinner } from '../components/LoadingSpinner';

const medicationSchema = z.object({
    name: z.string().min(1, 'Название обязательно'),
    type: z.string().min(1, 'Тип обязателен'),
    dosage: z.string().optional(),
    unit: z.string().optional(),
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

const COMMON_TYPES = ['Таблетка', 'Ингаляция', 'Капли', 'Укол', 'Мазь', 'Сироп', 'Другое...'];

export function MedicationForm() {
    const { id } = useParams<{ id: string }>();
    const isEditing = !!id;
    const navigate = useNavigate();
    const { selectedPetId } = usePet();
    const queryClient = useQueryClient();
    const [typePickerVisible, setTypePickerVisible] = useState(false);
    const [showCustomType, setShowCustomType] = useState(false);

    const { control, handleSubmit, reset, watch, formState: { errors, isSubmitting } } = useForm<MedicationFormData>({
        resolver: zodResolver(medicationSchema) as any,
        defaultValues: {
            name: '',
            type: '',
            dosage: '',
            unit: '',
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
                dosage: med.dosage || '',
                unit: med.unit || '',
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
            Toast.show({ icon: 'success', content: isEditing ? 'Курс обновлен' : 'Курс создан' });
            navigate('/medications');
        },
        onError: (err: any) => {
            Toast.show({ icon: 'fail', content: err?.response?.data?.error || 'Ошибка при сохранении' });
        }
    });

    const onSubmit = (data: MedicationFormData) => {
        // Validate inventory constraints
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
            if (data.inventory_warning_threshold !== null && data.inventory_warning_threshold !== undefined &&
                data.inventory_warning_threshold < 0) {
                Toast.show({ icon: 'fail', content: 'Порог предупреждения не может быть отрицательным' });
                return;
            }
        }
        mutation.mutate(data);
    };

    if (isEditing && isLoadingMed) return <LoadingSpinner />;

    return (
        <div style={{
            minHeight: '100vh',
            paddingTop: 'calc(env(safe-area-inset-top) + 88px)',
            paddingBottom: 'calc(env(safe-area-inset-bottom) + 80px)',
            backgroundColor: 'var(--app-page-background)',
            color: 'var(--app-text-color)'
        }}>
            <div style={{ maxWidth: '800px', margin: '0 auto', padding: '0 16px' }}>
                <h2 style={{ marginBottom: '16px', fontSize: '24px', fontWeight: 600 }}>
                    {isEditing ? 'Редактировать курс' : 'Новый прием препаратов'}
                </h2>

                <Form
                    layout="horizontal"
                    mode="card"
                    onFinish={handleSubmit(onSubmit)}
                >
                    <Form.Header>Основная информация</Form.Header>
                    <Controller
                        name="name"
                        control={control}
                        render={({ field }) => (
                            <Form.Item label="Название" required help={errors.name?.message}>
                                <Input
                                    value={field.value}
                                    onChange={field.onChange}
                                    placeholder="Напр. Сальбутамол"
                                    clearable
                                    style={{ '--text-align': 'right' }}
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
                                    label="Тип препарата"
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
                                        style={{ pointerEvents: 'none', '--text-align': 'right' }}
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
                                        }
                                        setTypePickerVisible(false);
                                    }}
                                    cancelText="Отмена"
                                    confirmText="Выбрать"
                                />
                                {showCustomType && (
                                    <Form.Item label="Свой тип препарата">
                                        <Input
                                            value={field.value}
                                            onChange={field.onChange}
                                            placeholder="Введите тип препарата"
                                            clearable
                                            style={{ '--text-align': 'right' }}
                                        />
                                    </Form.Item>
                                )}
                            </>
                        )}
                    />

                    <Controller
                        name="dosage"
                        control={control}
                        render={({ field }) => (
                            <Form.Item label="Дозировка">
                                <Input
                                    value={field.value}
                                    onChange={field.onChange}
                                    placeholder="Напр. 100"
                                    style={{ '--text-align': 'right' }}
                                />
                            </Form.Item>
                        )}
                    />
                    <Controller
                        name="unit"
                        control={control}
                        render={({ field }) => (
                            <Form.Item label="Единица измерения">
                                <Input
                                    value={field.value}
                                    onChange={field.onChange}
                                    placeholder="Напр. мкг, мл, таб"
                                    style={{ '--text-align': 'right' }}
                                />
                            </Form.Item>
                        )}
                    />

                    <Form.Header>Расписание</Form.Header>
                    <Form.Item
                        label="Дни приема"
                        required
                        help={errors.schedule?.days?.message}
                        layout="vertical"
                    >
                        <Controller
                            name="schedule.days"
                            control={control}
                            render={({ field }) => (
                                <Selector
                                    columns={4}
                                    options={DAYS_OF_WEEK}
                                    multiple
                                    value={field.value}
                                    onChange={(val) => field.onChange(val)}
                                    style={{ '--border-radius': '8px', padding: '4px 0' }}
                                />
                            )}
                        />
                    </Form.Item>

                    <Form.Item label="Время приема" required layout="vertical">
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', padding: '4px 0' }}>
                            {timeFields.map((timeField: any, index) => (
                                <div key={timeField.id} style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                                    <Controller
                                        name={`schedule.times.${index}` as any}
                                        control={control}
                                        render={({ field: tField }) => (
                                            <Input
                                                value={tField.value}
                                                onChange={tField.onChange}
                                                type="time"
                                                style={{
                                                    flex: 1,
                                                    padding: '8px 12px',
                                                    borderRadius: '8px',
                                                    border: '1px solid var(--app-border-color)',
                                                    backgroundColor: 'transparent'
                                                }}
                                            />
                                        )}
                                    />
                                    {timeFields.length > 1 && (
                                        <Button
                                            size="small"
                                            color="danger"
                                            fill="none"
                                            onClick={() => removeTime(index)}
                                            style={{ padding: '0 8px' }}
                                        >
                                            <DeleteOutline fontSize={20} />
                                        </Button>
                                    )}
                                </div>
                            ))}
                            <Button
                                size="small"
                                fill="outline"
                                color="primary"
                                onClick={() => appendTime('08:00')}
                                style={{ borderRadius: '8px', marginTop: '4px' }}
                            >
                                <AddOutline /> Добавить время
                            </Button>
                        </div>
                        {errors.schedule?.times?.message && (
                            <div style={{ color: 'var(--adm-color-danger)', fontSize: '12px', marginTop: '4px' }}>
                                {errors.schedule.times.message}
                            </div>
                        )}
                    </Form.Item>

                    <Form.Header>Инвентарь</Form.Header>
                    <Controller
                        name="inventory_enabled"
                        control={control}
                        render={({ field }) => (
                            <Form.Item
                                label="Следить за остатком"
                                extra={<Switch checked={field.value} onChange={field.onChange} />}
                            />
                        )}
                    />

                    {inventoryEnabled && (
                        <>
                            <Controller
                                name="inventory_total"
                                control={control}
                                render={({ field }) => (
                                    <Form.Item label="Всего в упаковке (доз)">
                                        <Input
                                            value={field.value?.toString() || ''}
                                            onChange={(val) => {
                                                const num = val === '' ? null : Number(val);
                                                field.onChange(isNaN(num as number) ? null : num);
                                            }}
                                            type="number"
                                            placeholder="Количество"
                                            style={{ '--text-align': 'right' }}
                                        />
                                    </Form.Item>
                                )}
                            />
                            <Controller
                                name="inventory_current"
                                control={control}
                                render={({ field }) => (
                                    <Form.Item label="Текущий остаток">
                                        <Input
                                            value={field.value?.toString() || ''}
                                            onChange={(val) => {
                                                const num = val === '' ? null : Number(val);
                                                field.onChange(isNaN(num as number) ? null : num);
                                            }}
                                            type="number"
                                            placeholder="Осталось в наличии"
                                            style={{ '--text-align': 'right' }}
                                        />
                                    </Form.Item>
                                )}
                            />
                            <Controller
                                name="inventory_warning_threshold"
                                control={control}
                                render={({ field }) => (
                                    <Form.Item label="Предупредить, когда останется">
                                        <Input
                                            value={field.value?.toString() || ''}
                                            onChange={(val) => {
                                                const num = val === '' ? null : Number(val);
                                                field.onChange(isNaN(num as number) ? null : num);
                                            }}
                                            type="number"
                                            placeholder="Порог предупреждения"
                                            style={{ '--text-align': 'right' }}
                                        />
                                    </Form.Item>
                                )}
                            />
                        </>
                    )}

                    <Form.Header>Дополнительно</Form.Header>
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
                                    placeholder="Любые заметки"
                                    clearable
                                    style={{ '--text-align': 'right' }}
                                />
                            </Form.Item>
                        )}
                    />
                </Form>

                <div style={{
                    marginTop: '8px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '12px',
                    padding: '0 16px 20px'
                }}>
                    <Button
                        block
                        color="primary"
                        size="large"
                        onClick={handleSubmit(onSubmit)}
                        loading={mutation.isPending || isSubmitting}
                        style={{ borderRadius: '12px', fontWeight: 600 }}
                    >
                        {isEditing ? 'Сохранить' : 'Создать'}
                    </Button>
                    <Button
                        block
                        onClick={() => navigate('/medications')}
                        style={{ borderRadius: '12px', fontWeight: 500 }}
                    >
                        Отмена
                    </Button>
                </div>
            </div>
        </div>
    );
}
