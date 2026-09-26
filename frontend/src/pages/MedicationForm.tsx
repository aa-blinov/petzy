import { useEffect, useState } from 'react';
import { showToast } from '../utils/toast';
import { getApiErrorMessage } from '../utils/apiError';
import { useNavigate, useParams } from 'react-router-dom';
import { goBack } from '../utils/navigation';
import { Button, Form, Input, Switch, Selector, Picker, Popup, List } from 'antd-mobile';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm, Controller, useFieldArray, useWatch } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { DeleteOutline, SearchOutline } from 'antd-mobile-icons';
import { medicationsService, type MedicationCreate, COMMON_MEDICATIONS } from '../services/medications.service';
import { usePet } from '../hooks/usePet';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { SpinnerButton } from '../components/SpinnerButton';
import { FieldError } from '../components/FieldError';
import { onInvalidSubmit } from '../utils/formErrors';
import { formatAmount, isAmountDraft, parseAmount } from '../utils/stock';
import { pluralRu } from '../utils/relativeTime';
import { FormDangerButton } from '../components/FormDangerButton';

/** A typed amount («0,5» or «0.5») for zod; '' is «not set». */
const amount = (v: unknown) => (v === '' || v === undefined || v === null ? null : typeof v === 'string' ? v.replace(',', '.') : v);

const medicationSchema = z.object({
    name: z.string().min(1, 'Введите название'),
    type: z.string().min(1, 'Выберите форму'),
    form_factor: z.string().optional(),
    strength: z.string().optional(),
    dose_unit: z.string().optional(),
    default_dose: z.preprocess(amount, z.coerce.number({ error: 'Введите число' }).min(0.0001, 'Доза должна быть больше нуля')),
    schedule: z.object({
        days: z.array(z.number()).min(1, 'Выберите хотя бы один день'),
        times: z.array(z.string().regex(/^([01]\d|2[0-3]):([0-5]\d)$/, 'Выберите время')).min(1, 'Добавьте хотя бы одно время'),
    }),
    inventory_enabled: z.boolean(),
    // Pack size: what «Пополнить» offers to add. Not a cap on the stock,
    // which can hold more than one pack.
    inventory_total: z.preprocess(amount, z.coerce.number({ error: 'Введите число' }).nullable().optional()),
    inventory_current: z.preprocess(amount, z.coerce.number({ error: 'Введите число' }).nullable().optional()),
    inventory_warning_days: z.preprocess(amount, z.coerce.number({ error: 'Введите число' }).min(0, 'Не меньше нуля').max(60, 'Не больше 60 дней').nullable().optional()),
    is_active: z.boolean(),
    comment: z.string().optional(),
}).superRefine((data, ctx) => {
    // Checked here rather than in onSubmit, where they were toasts with
    // no link to the field they were about.
    if (!data.inventory_enabled) return;
    const total = data.inventory_total as number | null | undefined;
    const current = data.inventory_current as number | null | undefined;
    if (total !== null && total !== undefined && total <= 0) {
        ctx.addIssue({ code: 'custom', path: ['inventory_total'], message: 'В упаковке должно быть больше нуля' });
    }
    if (current !== null && current !== undefined && current < 0) {
        ctx.addIssue({ code: 'custom', path: ['inventory_current'], message: 'Остаток не может быть меньше нуля' });
    }
});

type MedicationFormInput = z.input<typeof medicationSchema>;
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
    // Tracks the last med.type we derived showCustomType from, so the
    // derivation below runs during render (React's sanctioned pattern for
    // "adjust state when a prop/query result changes") instead of in an
    // effect, which would cause an extra cascading render.
    const [lastSeenMedType, setLastSeenMedType] = useState<string | undefined>(undefined);
    const [showCommonMeds, setShowCommonMeds] = useState(false);
    const [activeTimeIndex, setActiveTimeIndex] = useState<number | null>(null);
    const [timePickerVisible, setTimePickerVisible] = useState(false);
    const [unitPickerVisible, setUnitPickerVisible] = useState(false);

    // Time picker columns
    const hours = Array.from({ length: 24 }, (_, i) => ({ label: i.toString().padStart(2, '0'), value: i.toString().padStart(2, '0') }));
    const minutes = Array.from({ length: 60 }, (_, i) => ({ label: i.toString().padStart(2, '0'), value: i.toString().padStart(2, '0') }));

    const { control, handleSubmit, reset, setValue, formState: { errors, isSubmitting } } = useForm<MedicationFormInput, unknown, MedicationFormData>({
        // onInvalidSubmit scrolls to and focuses the first error in page order;
        // RHF's own focus picked the first registered ref instead.
        shouldFocusError: false,
        resolver: zodResolver(medicationSchema),
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
            inventory_warning_days: 3,
            is_active: true,
            comment: '',
        }
    });

    const { fields: timeFields, append: appendTime, remove: removeTime } = useFieldArray({
        control,
        name: 'schedule.times' as never,
    });

    // useWatch (a subscription) rather than calling watch() inline is
    // what React Compiler can actually verify is safe to memoize — watch()
    // returns a live function whose output it can't prove is stable.
    const inventoryEnabled = useWatch({ control, name: 'inventory_enabled' });
    const watchedDoseUnit = useWatch({ control, name: 'dose_unit' });
    const doseUnit = watchedDoseUnit || 'ед.';
    const watchedDoseUnitForPicker = watchedDoseUnit || 'ед';
    const watchedDefaultDose = useWatch({ control, name: 'default_dose' }) || 1;
    const watchedTimes = useWatch({ control, name: 'schedule.times' });
    const watchedDays = useWatch({ control, name: 'schedule.days' });
    const watchedCurrent = useWatch({ control, name: 'inventory_current' });
    // «Хватит примерно на 6 дней», live as the stock or schedule changes.
    const stockPreview = (() => {
        const current = parseAmount(String(watchedCurrent ?? ''));
        const dose = parseAmount(String(watchedDefaultDose ?? '')) || 1;
        const perDay = (dose * (watchedTimes?.length || 0) * (watchedDays?.length || 0)) / 7;
        if (current === null || current <= 0 || perDay <= 0) return '';
        const days = Math.floor(current / perDay);
        return days < 1 ? 'Хватит меньше чем на день' : `Хватит примерно на ${days} ${pluralRu(days, 'день', 'дня', 'дней')}`;
    })();

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
                // Shown the Russian way («0,5»); the schema reads either.
                default_dose: formatAmount(med.default_dose || 1),
                schedule: {
                    days: med.schedule.days,
                    times: med.schedule.times,
                },
                inventory_enabled: med.inventory_enabled,
                inventory_total: med.inventory_total != null ? formatAmount(med.inventory_total) : null,
                inventory_current: med.inventory_current != null ? formatAmount(med.inventory_current) : null,
                // Warned by amount before days existed: saving moves it to days.
                inventory_warning_days: med.inventory_warning_days ?? 3,
                is_active: med.is_active,
                comment: med.comment || '',
            });
        }
    }, [med, reset]);

    // Adjust showCustomType during render when a newly-loaded med's type
    // isn't one of the presets — see the lastSeenMedType comment above for
    // why this runs here instead of in a useEffect.
    if (med && med.type !== lastSeenMedType) {
        setLastSeenMedType(med.type);
        if (!COMMON_TYPES.includes(med.type)) {
            setShowCustomType(true);
        }
    }

    const handleCommonMedSelect = (common: typeof COMMON_MEDICATIONS[0]) => {
        setValue('name', common.name);
        setValue('type', common.type);
        setValue('form_factor', common.form_factor);
        setValue('strength', common.strength);
        setValue('dose_unit', common.dose_unit);
        setValue('default_dose', common.default_dose);
        setShowCommonMeds(false);
        showToast.success('Данные заполнены');
    };

    const mutation = useMutation({
        mutationFn: async (data: MedicationFormData) => {
            const payload: MedicationCreate = {
                ...data,
                pet_id: selectedPetId!,
                inventory_total: data.inventory_total ?? undefined,
                inventory_current: data.inventory_current ?? undefined,
                inventory_warning_days: data.inventory_warning_days ?? undefined,
            };
            if (isEditing && id) {
                await medicationsService.update(id, payload);
            } else {
                await medicationsService.create(payload);
            }
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['medications'] });
            showToast.success(isEditing ? 'Курс обновлён' : 'Курс создан', {
                afterClose: () => goBack(navigate, '/medications'),
            });
        },
        onError: (err: unknown) => {
            showToast.failure(getApiErrorMessage(err, 'Не удалось сохранить'));
        }
    });

    const onSubmit = (data: MedicationFormData) => {
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
                    <h1 style={{ margin: 0, fontSize: 'var(--text-xxl)', fontWeight: 600 }}>
                        {isEditing ? 'Редактировать курс' : 'Новый курс'}
                    </h1>
                    {!isEditing && (
                        <Button
                            size="small"
                            color="primary"
                            fill="outline"
                            onClick={() => setShowCommonMeds(true)}
                            style={{ borderRadius: 'var(--app-border-radius)', fontSize: 'var(--text-xs)' }}
                        >
                            <SearchOutline /> Шаблоны
                        </Button>
                    )}
                </div>

                <div>
                    <Form
                        layout="horizontal"
                        mode="card"
                        onFinish={handleSubmit(onSubmit, onInvalidSubmit)}
                        style={{ '--prefix-width': '7em' } as React.CSSProperties}
                    >
                        <Form.Header>Препарат</Form.Header>
                        <Controller
                            name="name"
                            control={control}
                            render={({ field }) => (
                                <Form.Item label="Название" required description={errors.name?.message ? <FieldError message={errors.name.message} /> : undefined}>
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
                                        description={errors.type?.message ? <FieldError message={errors.type.message} /> : undefined}
                                        style={{ cursor: 'pointer' }}
                                        arrow
                                    >
                                        <Input
                                            readOnly
                                            value={field.value}
                                            placeholder="Выберите форму"
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

                        <Form.Header>Схема приёма</Form.Header>
                        <Controller
                            name="default_dose"
                            control={control}
                            render={({ field }) => (
                                <Form.Item label="Разовая" required description={errors.default_dose?.message ? <FieldError message={errors.default_dose.message} /> : undefined}>
                                    <div style={{ display: 'flex', gap: 'var(--spacing-md)', alignItems: 'center' }}>
                                        <Input
                                            value={field.value?.toString()}
                                            onChange={val => {
                                                if (isAmountDraft(val)) field.onChange(val);
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
                                                    <button
                                                        type="button"
                                                        onClick={() => setUnitPickerVisible(true)}
                                                        style={{
                                                            width: '100%',
                                                            background: 'transparent',
                                                            border: 'none',
                                                            padding: 0,
                                                            textAlign: 'center',
                                                            color: 'var(--app-primary-text)',
                                                            cursor: 'pointer',
                                                            font: 'inherit',
                                                        }}
                                                        aria-label="Выбрать единицу измерения"
                                                    >
                                                        <Input
                                                            value={unitField.value}
                                                            readOnly
                                                            placeholder="ед."
                                                            style={{
                                                                '--text-align': 'center',
                                                                color: 'var(--app-primary-text)',
                                                                cursor: 'pointer'
                                                            }}
                                                        />
                                                    </button>
                                                )}
                                            />
                                        </div>
                                        <Picker
                                            columns={[['таб', 'мл', 'мг', 'капс', 'шт', 'ед'].map(u => ({ label: u, value: u }))]}
                                            visible={unitPickerVisible}
                                            onClose={() => setUnitPickerVisible(false)}
                                            value={[watchedDoseUnitForPicker]}
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
                                {/* Right under the chips it is about, not at the
                                    bottom of the whole schedule block. */}
                                {errors.schedule?.days?.message && <FieldError message={errors.schedule.days.message} />}
                            </div>

                            {timeFields.map((timeField: { id: string }, index) => (
                                <div key={timeField.id} style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
                                    <button
                                        type="button"
                                        style={{
                                            flex: 1,
                                            cursor: 'pointer',
                                            background: 'transparent',
                                            border: 'none',
                                            padding: 0,
                                            textAlign: 'left',
                                            font: 'inherit',
                                            color: 'inherit',
                                        }}
                                        onClick={() => {
                                            setActiveTimeIndex(index);
                                            setTimePickerVisible(true);
                                        }}
                                        aria-label={`Изменить время приёма ${index + 1}`}
                                    >
                                        <Controller
                                            name={`schedule.times.${index}` as `schedule.times.${number}`}
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
                                    </button>
                                    {timeFields.length > 1 && (
                                        <Button
                                            size="small"
                                            color="danger"
                                            fill="none"
                                            onClick={() => removeTime(index)}
                                            aria-label="Удалить это время"
                                        >
                                            <DeleteOutline fontSize={20} aria-hidden />
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
                            {(errors.schedule?.times?.message || errors.schedule?.times?.root?.message) && (
                                <FieldError message={errors.schedule?.times?.message || errors.schedule?.times?.root?.message} />
                            )}

                            <Picker
                                columns={[hours, minutes]}
                                visible={timePickerVisible}
                                onClose={() => {
                                    setTimePickerVisible(false);
                                    setActiveTimeIndex(null);
                                }}
                                value={activeTimeIndex !== null ? (watchedTimes?.[activeTimeIndex] || '08:00').split(':') : ['08', '00']}
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

                        <Form.Header>Учёт остатков</Form.Header>
                        <Controller
                            name="inventory_enabled"
                            control={control}
                            render={({ field }) => (
                                <Form.Item
                                    label="Включить"
                                    extra={<Switch checked={field.value} onChange={field.onChange} />}
                                    description={field.value ? `Будем списывать по ${formatAmount(parseAmount(String(watchedDefaultDose)) || 1)} ${doseUnit} за приём` : undefined}
                                />
                            )}
                        />

                        {inventoryEnabled && (
                            <>
                                <Controller
                                    name="inventory_current"
                                    control={control}
                                    render={({ field, fieldState: { error } }) => (
                                        <Form.Item
                                            label={`Сейчас осталось (${doseUnit})`}
                                            description={
                                                error?.message ? <FieldError message={error.message} /> : stockPreview || undefined
                                            }
                                        >
                                            <Input
                                                value={field.value !== null && field.value !== undefined ? String(field.value) : ''}
                                                onChange={val => {
                                                    if (isAmountDraft(val)) field.onChange(val === '' ? null : val);
                                                }}
                                                type="text"
                                                inputMode="decimal"
                                                placeholder="0"
                                            />
                                        </Form.Item>
                                    )}
                                />
                                <Controller
                                    name="inventory_total"
                                    control={control}
                                    render={({ field, fieldState: { error } }) => (
                                        <Form.Item
                                            label={`В упаковке (${doseUnit})`}
                                            description={
                                                error?.message
                                                    ? <FieldError message={error.message} />
                                                    : 'Подставится, когда нажмёте «Пополнить»'
                                            }
                                        >
                                            <Input
                                                value={field.value !== null && field.value !== undefined ? String(field.value) : ''}
                                                onChange={val => {
                                                    if (isAmountDraft(val)) field.onChange(val === '' ? null : val);
                                                }}
                                                type="text"
                                                inputMode="decimal"
                                                placeholder="Необязательно"
                                            />
                                        </Form.Item>
                                    )}
                                />
                                <Controller
                                    name="inventory_warning_days"
                                    control={control}
                                    render={({ field, fieldState: { error } }) => (
                                        <Form.Item
                                            label="Предупредить, когда останется на"
                                            description={error?.message ? <FieldError message={error.message} /> : undefined}
                                            extra={<span style={{ color: 'var(--app-text-secondary)' }}>{pluralRu(Number(field.value) || 0, 'день', 'дня', 'дней')}</span>}
                                        >
                                            <Input
                                                value={field.value !== null && field.value !== undefined ? String(field.value) : ''}
                                                onChange={val => {
                                                    if (val === '' || /^\d{0,2}$/.test(val)) field.onChange(val === '' ? null : val);
                                                }}
                                                type="text"
                                                inputMode="numeric"
                                                placeholder="3"
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
                        <SpinnerButton
                            loading={mutation.isPending || isSubmitting}
                            onClick={() => handleSubmit(onSubmit, onInvalidSubmit)()}
                            style={{ borderRadius: 'var(--radius-md)', fontWeight: 600, marginBottom: 'var(--spacing-md)' }}
                        >
                            {isEditing ? 'Сохранить' : 'Создать'}
                        </SpinnerButton>
                        <Button
                            block
                            size="large"
                            onClick={() => goBack(navigate, '/medications')}
                            style={{ borderRadius: 'var(--radius-md)', fontWeight: 500, marginBottom: 'var(--spacing-md)' }}
                        >
                            Отмена
                        </Button>
                        {isEditing && id && med && (
                            <FormDangerButton
                                label="Удалить курс"
                                confirmTitle="Удаление курса"
                                confirmContent={`Удалить курс «${med.name}» и всю его историю?`}
                                onConfirm={async () => {
                                    try {
                                        await medicationsService.delete(id);
                                    } catch (error) {
                                        showToast.failure(getApiErrorMessage(error, 'Не удалось удалить курс'));
                                        throw error;
                                    }
                                    await queryClient.invalidateQueries({ queryKey: ['medications'] });
                                    showToast.success('Курс удалён');
                                    goBack(navigate, '/medications');
                                }}
                            />
                        )}
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
