import { useEffect, useRef, useState } from 'react';
import { showToast } from '../utils/toast';
import { useUnsavedChangesGuard } from '../hooks/useUnsavedChangesGuard';
import { useSessionDraft } from '../hooks/useSessionDraft';
import { fieldNote } from '../components/FieldNote';
import { getApiErrorMessage } from '../utils/apiError';
import { useNavigate, useParams } from 'react-router-dom';
import { goBack } from '../utils/navigation';
import { Button, Form, Input, Switch, Selector, Picker } from 'antd-mobile';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm, Controller, useFieldArray, useWatch } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { DeleteOutline } from 'antd-mobile-icons';
import { medicationsService, type MedicationCreate, COMMON_MEDICATIONS } from '../services/medications.service';
import { usePet } from '../hooks/usePet';
import { Segmented } from '../components/Segmented';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { EmptyState } from '../components/EmptyState';
import { LoadError } from '../components/LoadError';
import { isMissing } from '../utils/notFound';
import { Pill } from 'lucide-react';
import { newFormKey } from '../utils/idempotency';
import { SpinnerButton } from '../components/SpinnerButton';
import { FieldError } from '../components/FieldError';
import { onInvalidSubmit } from '../utils/formErrors';
import { useTypedDateProblems } from '../hooks/useTypedDateProblems';
import { formatAmount, isAmountDraft, parseAmount } from '../utils/stock';
import { pluralRu } from '../utils/relativeTime';
import { FormDangerButton } from '../components/FormDangerButton';
import { PickerValue } from '../components/PickerValue';
import { ChoiceSheet } from '../components/ChoiceSheetField';
import { ProductPickerSheet } from '../components/ProductPickerSheet';
import { MEDICINE_GROUPS } from '../utils/medicineCatalog';
import { DatePickerField } from '../components/DatePickerField';
import { showUndo } from '../utils/undo';
import { deleteMedicationWithUndo, medicationDeleteText } from '../utils/medicationDelete';
import { getCurrentDate } from '../utils/dateUtils';
import { refreshMedicationViews } from '../utils/intakeViews';
import { ALL_WEEKDAYS, newCourseDefaults } from '../utils/medicationDefaults';

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
        days: z.array(z.number()),
        times: z.array(z.string().regex(/^([01]\d|2[0-3]):([0-5]\d)$/, 'Выберите время')),
    }),
    // «По необходимости»: no days and no times, a dose is marked when it is given.
    as_needed: z.boolean(),
    inventory_enabled: z.boolean(),
    // Pack size: what «Пополнить» offers to add. Not a cap on the stock,
    // which can hold more than one pack.
    inventory_total: z.preprocess(amount, z.coerce.number({ error: 'Введите число' }).nullable().optional()),
    inventory_current: z.preprocess(amount, z.coerce.number({ error: 'Введите число' }).nullable().optional()),
    inventory_warning_days: z.preprocess(amount, z.coerce.number({ error: 'Введите число' }).min(0, 'Не меньше нуля').max(60, 'Не больше 60 дней').nullable().optional()),
    is_active: z.boolean(),
    comment: z.string().optional(),
    // The course: when it began and ended (YYYY-MM-DD, '' for «not set»), what for, who prescribed it.
    started_on: z.string().optional(),
    ended_on: z.string().optional(),
    purpose: z.string().max(200).optional(),
    prescribed_by: z.string().max(100).optional(),
}).superRefine((data, ctx) => {
    if (data.started_on && data.ended_on && data.ended_on < data.started_on) {
        ctx.addIssue({ code: 'custom', path: ['ended_on'], message: 'Окончание раньше начала' });
    }
    // Checked here rather than in onSubmit, where they were toasts with
    // no link to the field they were about.
    // Two doses at one time are one dose: a second slot would ask to be marked twice.
    const times = data.schedule.times;
    if (!data.as_needed && data.schedule.days.length < 1) {
        ctx.addIssue({ code: 'custom', path: ['schedule', 'days'], message: 'Выберите хотя бы один день' });
    }
    if (!data.as_needed && times.length < 1) {
        ctx.addIssue({ code: 'custom', path: ['schedule', 'times'], message: 'Добавьте хотя бы одно время' });
    }
    const dup = times.findIndex((t, i) => times.indexOf(t) !== i);
    if (dup >= 0) {
        ctx.addIssue({ code: 'custom', path: ['schedule', 'times'], message: `Время ${times[dup]} указано дважды` });
    }
    if (!data.inventory_enabled) return;
    const total = data.inventory_total as number | null | undefined;
    const current = data.inventory_current as number | null | undefined;
    if (current === null || current === undefined || (current as unknown) === '') {
        ctx.addIssue({ code: 'custom', path: ['inventory_current'], message: 'Укажите остаток: без него учёт не работает' });
    }
    if (total !== null && total !== undefined && total <= 0) {
        ctx.addIssue({ code: 'custom', path: ['inventory_total'], message: 'В упаковке должно быть больше нуля' });
    }
    if (current !== null && current !== undefined && current < 0) {
        ctx.addIssue({ code: 'custom', path: ['inventory_current'], message: 'Остаток не может быть меньше нуля' });
    }
});

type MedicationFormInput = z.input<typeof medicationSchema>;
type MedicationFormData = z.infer<typeof medicationSchema>;

/** The time a new dose row starts at: an hour after the latest one, and not one that is already there. */
function nextFreeTime(times: string[] | undefined): string {
    const taken = new Set(times ?? []);
    const latest = (times ?? []).filter((t) => /^\d{2}:\d{2}$/.test(t)).sort().pop();
    let minutes = latest ? (Number(latest.slice(0, 2)) * 60 + Number(latest.slice(3)) + 60) % 1440 : 8 * 60;
    for (let i = 0; i < 24 * 60 && taken.has(`${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`); i += 1) {
        minutes = (minutes + 60) % 1440;
    }
    return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
}

/** The chip says the short name and a screen reader the whole one («Пн» alone is read as two letters). */
const dayLabel = (short: string, full: string) => (
    <>
        <span aria-hidden="true">{short}</span>
        <span className="sr-only">{full}</span>
    </>
);
const DAYS_OF_WEEK = [
    { label: dayLabel('Пн', 'Понедельник'), value: 0 },
    { label: dayLabel('Вт', 'Вторник'), value: 1 },
    { label: dayLabel('Ср', 'Среда'), value: 2 },
    { label: dayLabel('Чт', 'Четверг'), value: 3 },
    { label: dayLabel('Пт', 'Пятница'), value: 4 },
    { label: dayLabel('Сб', 'Суббота'), value: 5 },
    { label: dayLabel('Вс', 'Воскресенье'), value: 6 },
];

const COMMON_TYPES = ['Таблетка', 'Капсула', 'Ингаляция', 'Капли', 'Укол', 'Мазь', 'Гель', 'Сироп', 'Суспензия', 'Порошок', 'Спрей', 'Паста'];
/** The last line of the picker: a form that is not in the list is written in. */
const OTHER_TYPE = 'Другое…';

/** Units counted in pieces, and how «сколько … давать» says them. */
const PIECES_WORD: Record<string, string> = { 'таб': 'таблеток', 'капс': 'капсул', 'шт': 'штук' };

/** The unit a form is usually given in, filled in when none is chosen yet
 *  (an empty unit showed «ед.», which says nothing). */
const UNIT_FOR_TYPE: Record<string, string> = {
    'Таблетка': 'таб',
    'Капсула': 'капс',
    'Капли': 'кап',
    'Укол': 'мл',
    'Сироп': 'мл',
    'Суспензия': 'мл',
};

export function MedicationForm() {
    const { id } = useParams<{ id: string }>();
    const isEditing = !!id;
    const navigate = useNavigate();
    const { pets, selectedPetId, selectedPetName, selectPet, isFetched: petsFetched } = usePet();
    const queryClient = useQueryClient();
    const [typePickerVisible, setTypePickerVisible] = useState(false);
    const [showCustomType, setShowCustomType] = useState(false);
    // Tracks the last med.type we derived showCustomType from, so the
    // derivation below runs during render (React's sanctioned pattern for
    // "adjust state when a prop/query result changes") instead of in an
    // effect, which would cause an extra cascading render.
    const [lastSeenMedType, setLastSeenMedType] = useState<string | undefined>(undefined);
    const [namePickerOpen, setNamePickerOpen] = useState(false);
    const [activeTimeIndex, setActiveTimeIndex] = useState<number | null>(null);
    const [timePickerVisible, setTimePickerVisible] = useState(false);
    const [unitPickerVisible, setUnitPickerVisible] = useState(false);

    // Time picker columns
    const hours = Array.from({ length: 24 }, (_, i) => ({ label: i.toString().padStart(2, '0'), value: i.toString().padStart(2, '0') }));
    const minutes = Array.from({ length: 60 }, (_, i) => ({ label: i.toString().padStart(2, '0'), value: i.toString().padStart(2, '0') }));

    // A new course is daily and begins today; narrowing the week or moving the start is the optional part.
    const course = newCourseDefaults(getCurrentDate());
    const { control, handleSubmit, reset, setValue, getValues, formState: { errors, isSubmitting, isDirty, dirtyFields } } = useForm<MedicationFormInput, unknown, MedicationFormData>({
        // onInvalidSubmit scrolls to and focuses the first error in page order;
        // RHF's own focus picked the first registered ref instead.
        // Validated when a field is left, and after that as it changes: an error
        // shows as soon as it is known, not only after «Сохранить».
        mode: 'onTouched',
        shouldFocusError: false,
        resolver: zodResolver(medicationSchema),
        defaultValues: {
            name: '',
            type: '',
            form_factor: 'other',
            as_needed: false,
            strength: '',
            dose_unit: '',
            default_dose: 1,
            schedule: {
                days: course.days,
                times: ['08:00'],
            },
            inventory_enabled: false,
            inventory_warning_days: 3,
            is_active: true,
            comment: '',
            started_on: course.started_on,
            ended_on: '',
            purpose: '',
            prescribed_by: '',
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
    const doseUnit = watchedDoseUnit || 'шт.';
    const watchedDoseUnitForPicker = watchedDoseUnit || 'таб';
    const watchedDefaultDose = useWatch({ control, name: 'default_dose' }) || 1;
    // «50 таб за раз» is almost always the box's «50 мг» typed in the wrong
    // field; stock and reminders would then count 50 tablets a dose. A
    // note, not a block: some courses really are several pieces.
    const typedDose = parseAmount(String(watchedDefaultDose)) ?? 0;
    const doseLooksLikeStrength = (watchedDoseUnit ?? '') in PIECES_WORD && typedDose > 5;
    const asNeeded = useWatch({ control, name: 'as_needed' });
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

    // The course by its own address, not by looking for it in the chosen pet's list: that list
    // never holds a course of another pet, so opening a link to it answered «Такого лекарства
    // нет, его удалили или он не открыт вашему питомцу» while the course was right there and
    // access to it was fine. The server answers 404 for this request only when the course is
    // really gone or is not the caller's to see, so what is left on screen here is the truth.
    const { data: med, isLoading: isLoadingMed, isError: medError, error: medErr, refetch: refetchMed } = useQuery({
        queryKey: ['medication', id],
        queryFn: () => medicationsService.getById(id!),
        enabled: isEditing && !!id,
        retry: false,
    });

    // The course belongs to a pet, and the address names that pet: it becomes the chosen one, as
    // it does on the medical card. Until it is chosen this form would save the course under
    // whichever pet happened to be selected, so the form waits below rather than drawing.
    const coursePetId = med?.pet_id;
    const coursePet = coursePetId ? pets.find((p) => p._id === coursePetId) : undefined;
    useEffect(() => {
        if (coursePet && coursePet._id !== selectedPetId) selectPet(coursePet);
    }, [coursePet, selectedPetId, selectPet]);

    useEffect(() => {
        if (med) {
            reset({
                name: med.name,
                type: med.type,
                form_factor: med.form_factor || 'other',
                // The mode is a stored sign, not the emptiness of the schedule. A course
                // written before the sign came (the backend resolves those) still reads right.
                as_needed: med.as_needed ?? med.schedule.times.length === 0,
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
                started_on: med.started_on || '',
                ended_on: med.ended_on || '',
                purpose: med.purpose || '',
                prescribed_by: med.prescribed_by || '',
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

    // What this pet has been given before comes first in the list.
    const { data: petMedicines } = useQuery({
        queryKey: ['medications', selectedPetId, 'names'],
        queryFn: () => medicationsService.getList(selectedPetId!),
        enabled: !!selectedPetId,
    });
    const earlierMedicines = Array.from(new Set((petMedicines ?? []).map((m) => m.name.trim()).filter(Boolean)));

    const handleNamePick = (name: string) => {
        // shouldDirty: a chosen name, like a typed one, is unsaved data.
        const filled = { shouldDirty: true, shouldValidate: true };
        setValue('name', name, filled);
        setNamePickerOpen(false);
        const common = COMMON_MEDICATIONS.find((m) => m.name === name);
        if (!common) return;
        // A medicine known with its form and the strength of the box: those come along, the dose and the schedule are the vet's.
        setValue('type', common.type, filled);
        setValue('form_factor', common.form_factor, filled);
        setValue('strength', common.strength, filled);
        setValue('dose_unit', common.dose_unit, filled);
    };

    const { dialog: leaveDialog, release } = useUnsavedChangesGuard(isDirty);
    useSessionDraft({ dirty: isDirty, petId: id ?? null, getValues, reset, ready: !isEditing || !!med, release });

    // «Завершить курс»: switched off as of today, and undoable from the bar.
    const finishCourse = useMutation({
        mutationFn: async () => {
            await medicationsService.update(id!, { is_active: false, ended_on: getCurrentDate() });
        },
        onMutate: () => med?.ended_on ?? '',
        onSuccess: (_result, _vars, endedBefore) => {
            refreshMedicationViews(queryClient);
            release();
            showUndo({
                message: `${med?.name ?? 'Лекарство'}: курс завершён`,
                onUndo: async () => {
                    // The end date the course had before (a planned one) comes back with it, not only the switch.
                    await medicationsService.update(id!, { is_active: true, ended_on: endedBefore });
                    await refreshMedicationViews(queryClient);
                },
            });
            goBack(navigate, '/medications');
        },
        onError: (err: unknown) => {
            showToast.failure(getApiErrorMessage(err, 'Не удалось завершить курс'));
        },
    });

    // «Возобновить курс»: the way back from a finished one, with the end date cleared, undoable from the bar.
    const resumeCourse = useMutation({
        mutationFn: async () => {
            await medicationsService.update(id!, { is_active: true, ended_on: '' });
        },
        onSuccess: () => {
            refreshMedicationViews(queryClient);
            release();
            showUndo({
                message: `${med?.name ?? 'Лекарство'}: курс возобновлён`,
                onUndo: async () => {
                    await medicationsService.update(id!, { is_active: false, ended_on: med?.ended_on ?? getCurrentDate() });
                    await refreshMedicationViews(queryClient);
                },
            });
            goBack(navigate, '/medications');
        },
        onError: (err: unknown) => {
            showToast.failure(getApiErrorMessage(err, 'Не удалось возобновить курс'));
        },
    });

    // One key per opening of the form: a retry after a lost answer does not store the course twice.
    const formKey = useRef(newFormKey());
    const mutation = useMutation({
        mutationFn: async ({ data, stockEdited }: { data: MedicationFormData; stockEdited: boolean }) => {
            const payload: MedicationCreate = {
                ...data,
                // Days and times are saved as chosen, in either mode: switching the
                // mode on and back does not make the person enter them again.
                schedule: data.schedule,
                pet_id: selectedPetId!,
                inventory_total: data.inventory_total ?? undefined,
                // A course already saved takes its stock only when this edit changed it. The form holds the stock
                // of the moment it was opened, and another phone may have counted it down since: saving it back
                // would undo those doses. A new course has no stock on the server yet, so its stock always goes.
                inventory_current: !isEditing || stockEdited ? (data.inventory_current ?? undefined) : undefined,
                inventory_warning_days: data.inventory_warning_days ?? undefined,
            };
            if (isEditing && id) {
                await medicationsService.update(id, payload);
            } else {
                await medicationsService.create(payload, formKey.current);
                formKey.current = newFormKey();
            }
        },
        onSuccess: () => {
            refreshMedicationViews(queryClient);
            // Leave at once; the toast lives on over the list (waiting for
            // it to close kept a saved form on screen for two seconds).
            showToast.success(isEditing ? 'Лекарство сохранено' : 'Лекарство добавлено');
            release();
            goBack(navigate, '/medications');
        },
        onError: (err: unknown) => {
            showToast.failure(getApiErrorMessage(err, 'Не удалось сохранить'));
        }
    });

    // A typed date that is unfinished or impossible is not in the form's value: saving would keep the older one in silence.
    const typedDates = useTypedDateProblems();
    const submit = () => {
        typedDates.refuse();
        void handleSubmit(onSubmit, onInvalidSubmit)();
    };
    const onSubmit = (data: MedicationFormData) => {
        if (typedDates.blocked) return;
        // Changed means different from what the form loaded with: react-hook-form keeps the loaded values as defaults.
        mutation.mutate({ data, stockEdited: !!dirtyFields.inventory_current });
    };

    if (isEditing && isLoadingMed) return <LoadingSpinner />;

    // The course belongs to another pet and that pet is not the chosen one yet. Drawing the form
    // now would show the wrong pet's name and save the course under it, so the screen waits for
    // the switch above instead. `isFetched` keeps it waiting while the roster is still on its way;
    // once it has arrived and holds no such pet, the course is gone after all.
    const waitingForItsPet = isEditing && !!med && !!coursePetId && coursePetId !== selectedPetId
        && (!!coursePet || !petsFetched);
    if (waitingForItsPet) return <LoadingSpinner />;

    // The course is gone (deleted by someone else, closed from under us, or a link from an old
    // message): the request answered and refused. That is now the only way to get here, so the
    // words are true. Before, the form looked for the course in the chosen pet's list and said
    // this about any course of another pet. A request that never got an answer is not that: it offers to ask again.
    const medGone = isMissing(medErr);
    if (isEditing && !!id && !isLoadingMed && (medError || !med)) {
        if (medError && !medGone) {
            return (
                <div className="page-container">
                    <div className="max-width-container">
                        <LoadError what="лекарство" onRetry={refetchMed} />
                    </div>
                </div>
            );
        }
        return (
            <div className="page-container">
                <div className="max-width-container">
                    <EmptyState
                        icon={Pill}
                        title="Такого лекарства нет"
                        description="Его удалили или он не открыт вашему питомцу"
                        actionLabel="К лекарствам"
                        onAction={() => navigate('/medications', { replace: true })}
                    />
                </div>
            </div>
        );
    }

    return (
        <div className="page-container">
            <div className="max-width-container">
                <div className="safe-area-padding" style={{
                    marginBottom: selectedPetName ? 0 : 'var(--spacing-lg)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                }}>
                    <div className="screen-head">
                      <h1 className="screen-title" style={{ margin: 0, fontSize: 'var(--text-xxl)', fontWeight: 600 }}>
                          {isEditing ? 'Изменить лекарство' : 'Новое лекарство'}
                      </h1>
                    </div>
                </div>
                {/* The pet's name is the line the title is about, so it sits 4px under it (the
                    spacing table's title and the line it is about) and carries the room before
                    the form. The title block's own margin is that room only when there is no line. */}
                {selectedPetName && (
                    <p className="safe-area-padding" style={{ margin: 'var(--spacing-xs) 0 var(--spacing-md)', color: 'var(--app-text-secondary)' }}>
                        Питомец: <strong className="pet-name" style={{ color: 'var(--app-text-primary)' }}>{selectedPetName}</strong>
                    </p>
                )}

                <div>
                    <Form
                        layout="horizontal"
                        mode="card"
                        onFinish={submit}
                        style={{ '--prefix-width': '7em' } as React.CSSProperties}
                    >
                        <Form.Header>Лекарство</Form.Header>
                        <Controller
                            name="name"
                            control={control}
                            render={({ field }) => (
                                <Form.Item
                                    label="Название"
                                    required
                                    clickable
                                    arrow
                                    onClick={() => setNamePickerOpen(true)}
                                    description={
                                        errors.name?.message ? (
                                            <FieldError message={errors.name.message} />
                                        ) : (
                                            fieldNote({ hint: 'Не нашли в списке? Впишите название в поиске' })
                                        )
                                    }
                                >
                                    <PickerValue value={field.value} placeholder="Выберите или впишите" />
                                </Form.Item>
                            )}
                        />

                        <Controller
                            name="type"
                            control={control}
                            render={({ field }) => (
                                <>
                                    <Form.Item
                                        label="Форма выпуска"
                                        required
                                        onClick={() => setTypePickerVisible(true)}
                                        description={errors.type?.message ? <FieldError message={errors.type.message} /> : undefined}
                                        style={{ cursor: 'pointer' }}
                                        arrow
                                    >
                                        <PickerValue value={field.value} placeholder="Выберите" />
                                    </Form.Item>
                                    {(showCustomType || (!!field.value && !COMMON_TYPES.includes(field.value))) && (
                                        <Form.Item label="Какая форма" required>
                                            <Input value={field.value} onChange={field.onChange} placeholder="Например, ушные капли" maxLength={50} clearable />
                                        </Form.Item>
                                    )}
                                    {/* A list, not a wheel: a tap chooses and closes, and «Готово» cannot accept the first line unseen. */}
                                    <ChoiceSheet
                                        visible={typePickerVisible}
                                        title="Форма выпуска"
                                        options={[...COMMON_TYPES, OTHER_TYPE].map((t) => ({ label: t === OTHER_TYPE ? 'Другое' : t, value: t }))}
                                        onClose={() => setTypePickerVisible(false)}
                                        // A saved form that is not in the list stands on «Другое».
                                        value={showCustomType || (!!field.value && !COMMON_TYPES.includes(field.value)) ? OTHER_TYPE : field.value}
                                        onSelect={(selected) => {
                                            if (selected === OTHER_TYPE) {
                                                setShowCustomType(true);
                                                if (COMMON_TYPES.includes(field.value)) field.onChange('');
                                            } else {
                                                setShowCustomType(false);
                                                field.onChange(selected);

                                                if (!watchedDoseUnit && UNIT_FOR_TYPE[selected]) setValue('dose_unit', UNIT_FOR_TYPE[selected]);
                                                if (selected === 'Таблетка' || selected === 'Капсула') setValue('form_factor', 'tablet');
                                                else if (selected === 'Сироп' || selected === 'Суспензия' || selected === 'Капли') setValue('form_factor', 'liquid');
                                                else if (selected === 'Укол') setValue('form_factor', 'injection');
                                            }
                                            setTypePickerVisible(false);
                                        }}
                                    />
                                </>
                            )}
                        />

                        <Controller
                            name="strength"
                            control={control}
                            render={({ field }) => (
                                <Form.Item
                                    label="На упаковке"
                                    description={fieldNote({
                                        hint: 'Сколько вещества в одной таблетке или в 1 мл, как написано на коробке',
                                        value: field.value,
                                        max: 50,
                                    })}
                                >
                                    <Input
                                        onBlur={field.onBlur}
                                        value={field.value}
                                        onChange={field.onChange}
                                        placeholder="Например, 300 мг или 0,5 мг/мл"
                                        maxLength={50}
                                    />
                                </Form.Item>
                            )}
                        />

                        <Form.Header>Схема приёма</Form.Header>
                        <Controller
                            name="default_dose"
                            control={control}
                            render={({ field }) => (
                                <Form.Item
                                    label="За один приём"
                                    required
                                    description={
                                        errors.default_dose?.message ? (
                                            <FieldError message={errors.default_dose.message} />
                                        ) : doseLooksLikeStrength ? (
                                            <span style={{ color: 'var(--app-warning-text)' }}>
                                                {/* The other field by its own label: «выше» pointed at a direction, and
                                                    the box field sits two rows up, not immediately above. */}
                                                {formatAmount(typedDose)} {watchedDoseUnit} за раз? Если это миллиграммы с упаковки, впишите их в «На упаковке», а здесь укажите, сколько {PIECES_WORD[watchedDoseUnit ?? ''] ?? 'штук'} давать
                                            </span>
                                        ) : (
                                            'Сколько давать за раз. Для половины таблетки впишите 0,5'
                                        )
                                    }
                                >
                                    <div style={{ display: 'flex', gap: 'var(--spacing-md)', alignItems: 'center' }}>
                                        <Input
                                            onBlur={field.onBlur}
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
                                                        // The 44px to press come from the hit area, not from the height: a taller row would
                                                        // push the amount off the line of its label.
                                                        className="touch-target"
                                                        onClick={() => setUnitPickerVisible(true)}
                                                        style={{
                                                            display: 'block',
                                                            width: '100%',
                                                            height: 24,
                                                            lineHeight: '24px',
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
                                                        <PickerValue
                                                            value={unitField.value}
                                                            placeholder="Единица"
                                                            style={{ textAlign: 'center', color: 'var(--app-primary-text)', lineHeight: '24px' }}
                                                        />
                                                    </button>
                                                )}
                                            />
                                        </div>
                                        <Picker
                                            columns={[['таб', 'капс', 'мл', 'кап', 'мг', 'шт', 'ед'].map(u => ({ label: u, value: u }))]}
                                            visible={unitPickerVisible}
                                            onClose={() => setUnitPickerVisible(false)}
                                            value={[watchedDoseUnitForPicker]}
                                            onConfirm={v => {
                                                if (v[0]) setValue('dose_unit', v[0] as string);
                                            }}
                                            cancelText="Отмена"
                                            confirmText="Готово"
                                        />
                                    </div>
                                </Form.Item>
                            )}
                        />

                        <Form.Item label="Частота" required layout="vertical">
                            <div style={{ marginBottom: 'var(--spacing-lg)' }}>
                                <Segmented
                                    label="Как давать"
                                    value={asNeeded ? 'as_needed' : 'schedule'}
                                    options={[{ value: 'schedule', label: 'По расписанию' }, { value: 'as_needed', label: 'По необходимости' }]}
                                    onChange={(mode) => {
                                        const needed = mode === 'as_needed';
                                        setValue('as_needed', needed, { shouldDirty: true });
                                        if (needed) return;
                                        // The days and times a course was written with stay in the form while
                                        // the mode flips, so returning to a schedule fills in what is missing
                                        // rather than starting from an empty week.
                                        if ((getValues('schedule.times') ?? []).length === 0) {
                                            setValue('schedule.times', ['08:00'], { shouldDirty: true });
                                        }
                                        if ((getValues('schedule.days') ?? []).length === 0) {
                                            setValue('schedule.days', [...ALL_WEEKDAYS], { shouldDirty: true });
                                        }
                                    }}
                                />
                            </div>
                            {asNeeded ? (
                                <div style={{ fontSize: 'var(--text-sm)', color: 'var(--app-text-secondary)', lineHeight: 1.5 }}>
                                    Без напоминаний. Приём отмечается кнопкой «Дали сейчас» на карточке, когда лекарство дали
                                </div>
                            ) : (
                            <>
                            <div style={{ marginBottom: 'var(--spacing-lg)' }}>
                                <Controller
                                    name="schedule.days"
                                    control={control}
                                    render={({ field }) => (
                                        <Selector
                                            className="selector-chips"
                                            aria-label="Дни недели"
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
                                                <PickerValue
                                                    value={tField.value}
                                                    placeholder="Выберите время"
                                                    style={{
                                                        padding: '10px 12px', /* Roughly var(--spacing-md) */
                                                        borderRadius: 'var(--radius-sm)',
                                                        backgroundColor: 'var(--app-page-background)',
                                                        fontSize: 'var(--text-md)',
                                                        fontWeight: 500,
                                                        textAlign: 'center',
                                                    }}
                                                />
                                            )}
                                        />
                                    </button>
                                    {timeFields.length > 1 && (
                                        <Button
                                            size="small"
                                            color="danger"
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
                                onClick={() => appendTime(nextFreeTime(watchedTimes))}
                                style={{ marginTop: 'var(--spacing-xs)' }}
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
                                confirmText="Готово"
                                title="Выберите время"
                            />
                            </>
                            )}
                        </Form.Item>

                        <Controller
                            name="inventory_enabled"
                            control={control}
                            render={({ field }) => (
                                <Form.Item
                                    label="Следить за остатком"
                                    // The whole row toggles, not only the small switch (which stops its own tap from reaching the row).
                                    clickable
                                    arrow={false}
                                    onClick={() => field.onChange(!field.value)}
                                    extra={
                                        <span onClick={(event) => event.stopPropagation()}>
                                            <Switch aria-label="Следить за остатком" checked={field.value} onChange={field.onChange} />
                                        </span>
                                    }
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
                                            label="Остаток"
                                            className="form-item--unit"
                                            extra={<span style={{ color: 'var(--app-text-secondary)' }}>{doseUnit}</span>}
                                            description={
                                                error?.message ? <FieldError message={error.message} /> : stockPreview || undefined
                                            }
                                        >
                                            <Input
                                                onBlur={field.onBlur}
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
                                            label="В упаковке"
                                            className="form-item--unit"
                                            extra={<span style={{ color: 'var(--app-text-secondary)' }}>{doseUnit}</span>}
                                            description={
                                                error?.message
                                                    ? <FieldError message={error.message} />
                                                    : 'Подставится, когда нажмёте «Пополнить»'
                                            }
                                        >
                                            <Input
                                                onBlur={field.onBlur}
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
                                            label="Напомнить за"
                                            className="form-item--unit"
                                            description={
                                                error?.message ? (
                                                    <FieldError message={error.message} />
                                                ) : (
                                                    // The 60-day ceiling is said here, not only in the error
                                                    // that appears after the value is refused: a stock that
                                                    // lasts a season is not what this field can warn about.
                                                    'До того, как лекарство закончится, не больше 60 дней'
                                                )
                                            }
                                            extra={<span style={{ color: 'var(--app-text-secondary)' }}>{pluralRu(Number(field.value) || 0, 'день', 'дня', 'дней')}</span>}
                                        >
                                            <Input
                                                onBlur={field.onBlur}
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

                        <Form.Header>Курс</Form.Header>
                        <Controller
                            name="purpose"
                            control={control}
                            render={({ field }) => (
                                <Form.Item label="От чего" description={fieldNote({ value: field.value, max: 200 })}>
                                    <Input
                                        onBlur={field.onBlur}
                                        value={field.value}
                                        onChange={field.onChange}
                                        placeholder="Необязательно"
                                        maxLength={200}
                                        style={{ '--text-align': 'left' }}
                                    />
                                </Form.Item>
                            )}
                        />
                        <Controller
                            name="prescribed_by"
                            control={control}
                            render={({ field }) => (
                                <Form.Item label="Назначил" description={fieldNote({ value: field.value, max: 100 })}>
                                    <Input
                                        onBlur={field.onBlur}
                                        value={field.value}
                                        onChange={field.onChange}
                                        placeholder="Необязательно"
                                        maxLength={100}
                                        style={{ '--text-align': 'left' }}
                                    />
                                </Form.Item>
                            )}
                        />
                        <div className="datepair">
                        <Controller
                            name="started_on"
                            control={control}
                            render={({ field }) => (
                                <DatePickerField
                                    label="Начало"
                                    value={field.value ?? ''}
                                    onChange={field.onChange}
                                    onBlur={field.onBlur}
                                    onTypedProblem={typedDates.report('started_on')}
                                    refusals={typedDates.refusals}
                                    yearsBack={5}
                                    yearsForward={1}
                                    clearLabel="Убрать дату начала"
                                    placeholder="Не указано"
                                />
                            )}
                        />
                        <Controller
                            name="ended_on"
                            control={control}
                            render={({ field, fieldState: { error } }) => (
                                <DatePickerField
                                    label="Окончание"
                                    value={field.value ?? ''}
                                    onChange={field.onChange}
                                    onBlur={field.onBlur}
                                    onTypedProblem={typedDates.report('ended_on')}
                                    refusals={typedDates.refusals}
                                    yearsBack={5}
                                    yearsForward={1}
                                    clearLabel="Убрать дату окончания"
                                    placeholder="Не указано"
                                    description={error?.message ? <FieldError message={error.message} /> : 'Последний день курса: в этот день приёмы ещё предлагаются, со следующего нет'}
                                />
                            )}
                        />
                        </div>
                        <Controller
                            name="comment"
                            control={control}
                            render={({ field }) => (
                                <Form.Item label="Заметка" description={fieldNote({ value: field.value, max: 500 })}>
                                    <Input
                                        onBlur={field.onBlur}
                                        value={field.value}
                                        onChange={field.onChange}
                                        placeholder="Например, давать с едой"
                                        maxLength={500}
                                        style={{ '--text-align': 'left' }}
                                    />
                                </Form.Item>
                            )}
                        />
                    </Form>

                    {/* A long form: the main button stays above the tab bar, not three screens down. */}
                    <div className="form-sticky-action safe-area-padding">
                        <SpinnerButton loading={mutation.isPending || isSubmitting} onClick={submit}>
                            {/* «Добавить» for a new course, as on the document form («Сохранить» while editing). */}
                            {isEditing ? 'Сохранить' : 'Добавить'}
                        </SpinnerButton>
                    </div>
                    <div className="safe-area-padding form-actions" style={{ paddingBottom: 'var(--spacing-xl)' }}>
                        <Button
                            block
                            size="large"
                            onClick={() => goBack(navigate, '/medications')}
                        >
                            Отмена
                        </Button>
                        {isEditing && id && med && (
                            med.course_status !== 'ended' ? (
                                <Button
                                    block
                                    size="large"
                                    fill="outline"
                                    loading={finishCourse.isPending}
                                    disabled={finishCourse.isPending}
                                    onClick={() => finishCourse.mutate()}
                                >
                                    Завершить курс
                                </Button>
                            ) : (
                                <Button
                                    block
                                    size="large"
                                    fill="outline"
                                    loading={resumeCourse.isPending}
                                    disabled={resumeCourse.isPending}
                                    onClick={() => resumeCourse.mutate()}
                                >
                                    Возобновить курс
                                </Button>
                            )
                        )}
                        {isEditing && id && med && (
                            <FormDangerButton
                                label="Удалить лекарство"
                                confirmTitle="Удаление лекарства"
                                confirmContent={medicationDeleteText(med.name)}
                                onConfirm={async () => {
                                    deleteMedicationWithUndo(med, queryClient);
                                    release();
                                    goBack(navigate, '/medications');
                                }}
                            />
                        )}
                    </div>
                </div>
            </div>

            <ProductPickerSheet
                visible={namePickerOpen}
                title="Лекарство"
                placeholder="Название лекарства"
                groups={MEDICINE_GROUPS}
                earlier={earlierMedicines}
                onClose={() => setNamePickerOpen(false)}
                onPick={(name) => handleNamePick(name)}
            />
            {leaveDialog}
        </div>
    );
}
