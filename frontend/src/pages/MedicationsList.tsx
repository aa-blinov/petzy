import { useEffect, useMemo, useState } from 'react';
import { formatTime } from '../utils/dateUtils';
import { pluralRu } from '../utils/relativeTime';
import { toDeviceClock } from '../utils/timezone';
import { deleteMedicationWithUndo, medicationDeleteText } from '../utils/medicationDelete';
import { useHiddenRecords } from '../utils/deferredDelete';
import { PendingIntakesNotice } from '../components/PendingIntakesNotice';
import { showToast } from '../utils/toast';
import { getApiErrorMessage } from '../utils/apiError';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, Card, Dialog, Input, Popup, PullToRefresh, SearchBar } from 'antd-mobile';
import { ClockCircleOutline } from 'antd-mobile-icons';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Pill, Droplets, Syringe, Pencil, Trash2 } from 'lucide-react';
import { medicationsListQuery, medicationsService, type IntakeInput, type Medication } from '../services/medications.service';
import { IntakeDeclined, logIntakeAsking } from '../utils/duplicateIntake';
import { usePet } from '../hooks/usePet';
import { useAuth } from '../hooks/useAuth';
import { MedicationCardSkeleton, SkeletonList } from '../components/Skeletons';
import { EmptyState } from '../components/EmptyState';
import { PushOffNotice } from '../components/PushOffNotice';
import { LoadError } from '../components/LoadError';
import { UserAvatar } from '../components/UserAvatar';
import { hapticFeedback } from '../utils/haptic';
import { INTAKE_UNDO_MS, formatAmount, isAmountDraft, parseAmount, stockSummary } from '../utils/stock';
import { refreshAfterIntake } from '../utils/intakeViews';
import { showUndo } from '../utils/undo';
import { CardChevron } from '../components/CardChevron';
import { SwipeableRow } from '../components/SwipeableRow';
import { IntakeTimePicker } from '../components/IntakeTimePicker';
import { DraggableSheetBody } from '../components/DraggableSheetBody';
import { Fab } from '../components/Fab';
import { minutesAgo, nowWhen, whenLabel, whenPhrase, yesterdayEvening, type IntakeWhen } from '../utils/intakeWhen';
import { ChoiceChip, ChoiceChips } from '../components/ChoiceChips';
import { getCurrentDate } from '../utils/dateUtils';

/** Today's next unhandled slot of a course, once its time has come: a
 *  dose marked late was most likely given then. */
function pastSlotToday(med: Medication): string | null {
    const now = new Date();
    if (!med.schedule.days.includes((now.getDay() + 6) % 7)) return null;
    const slot = med.open_slots_today ? med.open_slots_today[0] : [...med.schedule.times].sort()[med.intakes_today || 0];
    return slot && slot <= formatTime(now) ? slot : null;
}

/** «Сегодня 1 из 3, не отмечено в 06:00, дальше в 23:30»: what is done, what was missed (its time has gone and nothing closed it),
 *  and what is still to come. The earliest open slot is not «дальше» when its hour is already behind. */
function todayProgress(med: Medication): string {
    const open = med.open_slots_today ?? [];
    const total = med.schedule.times.length;
    const now = formatTime(new Date());
    const missed = open.filter((t) => t <= now);
    const next = open.find((t) => t > now);
    return [
        `Сегодня ${total - open.length} из ${total}`,
        missed.length > 0 ? `не отмечено в ${missed.join(', ')}` : '',
        next ? `дальше в ${next}` : '',
    ]
        .filter(Boolean)
        .join(', ');
}

/** Every dose of today's schedule is handled. A course with nothing scheduled today (a dose when needed) is never done. */
function doneToday(med: Medication): boolean {
    if (med.open_slots_today) return !!med.scheduled_today && med.open_slots_today.length === 0;
    return (med.intakes_today || 0) >= med.schedule.times.length;
}

/** «Когда дали» in the intake dialog: now, at the slot, or a picked time. */
type WhenChoice = 'now' | 'slot' | 'other';

const ruDate = (iso: string) => new Date(`${iso.slice(0, 10)}T00:00:00`).toLocaleDateString('ru-RU');

/** The badge by the name: «Архив» for a course that is over, when it starts for one still to come. */
function courseTag(med: Medication): string | null {
    if (med.course_status === 'planned' && med.started_on) return `Начнётся ${ruDate(med.started_on)}`;
    if (med.course_status === 'ended' || (!med.course_status && !med.is_active)) return 'Архив';
    return null;
}

/** «С 12.05.2026 по 26.05.2026», from the dates the course has. */
function coursePeriod(med: Medication): string | null {
    if (med.started_on && med.ended_on) return `С ${ruDate(med.started_on)} по ${ruDate(med.ended_on)} включительно`;
    if (med.ended_on) return `До ${ruDate(med.ended_on)} включительно`;
    if (med.started_on && med.course_status !== 'planned') return `С ${ruDate(med.started_on)}`;
    return null;
}

export function MedicationsList() {
    const { selectedPetId } = usePet();
    const { username: currentUsername } = useAuth();
    const navigate = useNavigate();
    const queryClient = useQueryClient();

    const { data: medications = [], isLoading, isError, refetch } = useQuery({
        ...medicationsListQuery(selectedPetId ?? ''),
        enabled: !!selectedPetId,
    });

    // What is to be given first comes first: the course whose next unmarked dose is the earliest, then the ones done for
    // today, then those still to begin, and the finished ones last (the order of creation put the oldest, often the most
    // overdue, at the bottom).
    // A course deleted a moment ago, «Отменить» still on offer, is already out of the list.
    const hiddenMedications = useHiddenRecords();
    const orderedMedications = useMemo(() => {
        const rank = (m: Medication): [number, string] => {
            const status = m.course_status ?? (m.is_active ? 'active' : 'ended');
            if (status === 'ended') return [3, ''];
            if (status === 'planned') return [2, m.started_on ?? ''];
            const next = m.open_slots_today?.[0];
            return next ? [0, next] : [1, ''];
        };
        return medications.filter((m) => !hiddenMedications.has(m._id)).sort((a, b) => {
            const [ra, ta] = rank(a);
            const [rb, tb] = rank(b);
            return ra - rb || ta.localeCompare(tb);
        });
    }, [medications, hiddenMedications]);

    // Finished courses are folded under one line, and a long list can be searched.
    const isEnded = (m: Medication) => (m.course_status ? m.course_status === 'ended' : !m.is_active);
    const endedCount = orderedMedications.filter(isEnded).length;
    const [showEnded, setShowEnded] = useState(false);
    const [search, setSearch] = useState('');
    const needle = search.trim().toLowerCase();
    const shownMedications = orderedMedications.filter((m) => {
        if (needle) return m.name.toLowerCase().includes(needle);
        return showEnded || endedCount === orderedMedications.length || !isEnded(m);
    });

    const [logIntakeDialog, setLogIntakeDialog] = useState<{
        visible: boolean;
        medication: Medication | null;
        // Typed text, not a number: «0,» mid-typing must survive.
        dose: string;
        choice: WhenChoice;
        slot: string | null;
        other: IntakeWhen | null;
        // Which of the «a little while ago» chips was taken, so that it can be shown as chosen.
        ago: string | null;
    }>({
        visible: false,
        medication: null,
        dose: '1',
        choice: 'now',
        slot: null,
        other: null,
        ago: null,
    });
    const [whenPickerVisible, setWhenPickerVisible] = useState(false);
    const [justGiven, setJustGiven] = useState<string[]>([]);

    const [deleteDialog, setDeleteDialog] = useState<{
        visible: boolean;
        medication: Medication | null;
    }>({
        visible: false,
        medication: null
    });

    const intakeMutation = useMutation({
        mutationFn: ({ id, dose, when, skipped, slot }: { id: string; dose?: number; when: IntakeWhen; skipped?: boolean; slot?: string | null }) => {
            // «По расписанию»: the slot picked is the one that closes, however late the dose is marked.
            const input: IntakeInput = { ...when, dose_taken: dose, skipped, ...(slot ? { slot_date: nowWhen().date, slot_time: slot } : {}) };
            return logIntakeAsking(id, medications.find((m) => m._id === id)?.name ?? 'Лекарство', input);
        },
        onSuccess: ({ id, ran_out, queued }, { id: medId, skipped, when }) => {
            if (queued) {
                showToast.info('Нет связи. Отметка сохранена на телефоне и отправится сама');
                return;
            }
            refreshAfterIntake(queryClient);
            const name = medications.find((m) => m._id === medId)?.name ?? 'Приём';
            const now = nowWhen();
            const atNow = when.date === now.date && when.time === now.time;
            // A tap by mistake is undone from the bar, as on the feed.
            showUndo({
                duration: INTAKE_UNDO_MS,
                message: skipped
                    ? `${name}: приём пропущен`
                    : ran_out
                        ? `${name}: принято, лекарство закончилось. Пополните остаток`
                        : atNow
                            ? `${name}: приём отмечен`
                            : `${name}: отмечено, дали ${whenPhrase(when)}`,
                onUndo: async () => {
                    await medicationsService.deleteIntake(id);
                    await refreshAfterIntake(queryClient);
                },
            });
        },
        onError: (err: unknown) => {
            if (err instanceof IntakeDeclined) return;
            showToast.failure(getApiErrorMessage(err, 'Не удалось сохранить'));
        }
    });

    // «Завершить курс» and «Возобновить» from the list: the course is switched off as of today, or on again, and the bar takes it back.
    const toggleCourse = async (med: Medication) => {
        const ended = med.course_status ? med.course_status === 'ended' : !med.is_active;
        const refresh = async () => {
            await queryClient.invalidateQueries({ queryKey: ['medications'] });
            await queryClient.invalidateQueries({ queryKey: ['medical-card'] });
        };
        try {
            if (ended) {
                await medicationsService.update(med._id, { is_active: true, ended_on: '' });
            } else {
                await medicationsService.update(med._id, { is_active: false, ended_on: getCurrentDate() });
            }
            await refresh();
            showUndo({
                message: ended ? `Курс «${med.name}» возобновлён` : `Курс «${med.name}» завершён`,
                onUndo: async () => {
                    await medicationsService.update(med._id, ended ? { is_active: false, ended_on: med.ended_on ?? getCurrentDate() } : { is_active: true, ended_on: med.ended_on ?? '' });
                    await refresh();
                },
            });
        } catch (err) {
            showToast.failure(getApiErrorMessage(err, ended ? 'Не удалось возобновить курс' : 'Не удалось завершить курс'));
        }
    };

    const handleDelete = (med: Medication) => {
        hapticFeedback('light');
        setDeleteDialog({ visible: true, medication: med });
    };

    const handleLogIntake = (med: Medication) => {
        hapticFeedback('light');
        setLogIntakeDialog({
            visible: true,
            medication: med,
            dose: formatAmount(med.default_dose || 1),
            choice: 'now',
            slot: pastSlotToday(med),
            other: null,
            ago: null,
        });
    };

    // Both from the local wall clock, not toISOString(): that emits the
    // UTC date, which disagrees with the local date for several hours
    // around midnight (5 at UTC+5) — the intake landed under yesterday's
    // date paired with today's time, so it fell outside every "today"
    // query (intakes_today, the upcoming-dose widget).
    const chosenWhen = (): IntakeWhen => {
        const { choice, slot, other } = logIntakeDialog;
        if (choice === 'slot' && slot) return { date: nowWhen().date, time: slot };
        if (choice === 'other' && other) return other;
        return nowWhen();
    };

    // «Дали сейчас»: written at once with the course's own dose, the bar takes it back; the dialog is for the rest.
    const logNow = (med: Medication) => {
        // The same tap twice (a finger that lands twice) must not write two doses: the button waits a moment, and a dose given
        // on purpose again is a few seconds away (or goes through «Другое время или доза»).
        if (justGiven.includes(med._id)) return;
        setJustGiven((ids) => [...ids, med._id]);
        window.setTimeout(() => setJustGiven((ids) => ids.filter((id) => id !== med._id)), 3000);
        hapticFeedback('light');
        // The dose closes the slot whose time has come and nothing closed (as the dose widget on the feed does), not the one that is
        // nearest in time: given late for the morning, it must not close the evening one and silence its reminder.
        intakeMutation.mutate({ id: med._id, dose: med.default_dose || 1, when: nowWhen(), slot: pastSlotToday(med) });
    };

    const confirmLogIntake = () => {
        if (!logIntakeDialog.medication) return;
        const dose = parseAmount(logIntakeDialog.dose);
        if (!dose || dose <= 0) {
            showToast.failure('Укажите, сколько дали');
            return;
        }
        intakeMutation.mutate({ id: logIntakeDialog.medication._id, dose, when: chosenWhen(), slot: logIntakeDialog.choice === 'slot' ? logIntakeDialog.slot : null });
        setLogIntakeDialog(prev => ({ ...prev, visible: false }));
    };

    // On purpose, not by accident: nothing leaves the stock, the slot
    // counts as handled. It sits at the slot when there is one.
    const skipIntake = () => {
        if (!logIntakeDialog.medication) return;
        const { slot } = logIntakeDialog;
        intakeMutation.mutate({
            id: logIntakeDialog.medication._id,
            when: slot ? { date: nowWhen().date, time: slot } : nowWhen(),
            skipped: true,
            slot,
        });
        setLogIntakeDialog(prev => ({ ...prev, visible: false }));
    };

    // «Пополнить»: add a bought pack without doing the sum in the edit form.
    const [restock, setRestock] = useState<{ medication: Medication | null; amount: string }>({
        medication: null,
        amount: '',
    });
    const restockMutation = useMutation({
        mutationFn: ({ id, amount }: { id: string; amount: number }) => medicationsService.restock(id, amount),
        onSuccess: (current, { id }) => {
            queryClient.invalidateQueries({ queryKey: ['medications'] });
            const med = medications.find((m) => m._id === id);
            showToast.success(`Остаток пополнен: ${formatAmount(current)} ${med?.dose_unit || 'доз'}`);
        },
        onError: (err: unknown) => {
            showToast.failure(getApiErrorMessage(err, 'Не удалось пополнить остаток'));
        },
    });
    const openRestock = (med: Medication) => {
        hapticFeedback('light');
        // A pack size saved on the course is the likely amount.
        setRestock({ medication: med, amount: med.inventory_total ? formatAmount(med.inventory_total) : '' });
    };
    // The dose card's «Пополнить» arrives here with the course in the address.
    const [searchParams, setSearchParams] = useSearchParams();
    const restockId = searchParams.get('restock');
    useEffect(() => {
        if (!restockId) return;
        const med = medications.find((m) => m._id === restockId);
        if (!med) return;
        openRestock(med);
        setSearchParams((params) => {
            params.delete('restock');
            return params;
        }, { replace: true });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [restockId, medications]);
    const confirmRestock = () => {
        if (!restock.medication) return;
        const amount = parseAmount(restock.amount);
        if (!amount || amount <= 0) {
            showToast.failure('Укажите, сколько купили');
            return;
        }
        restockMutation.mutate({ id: restock.medication._id, amount });
        setRestock((prev) => ({ ...prev, medication: null }));
    };

    const formatRelativeTime = (dateStr?: string) => {
        if (!dateStr) return null;
        const date = new Date(dateStr);
        const now = new Date();
        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const yesterday = new Date(today);
        yesterday.setDate(yesterday.getDate() - 1);

        const datePart = new Date(date.getFullYear(), date.getMonth(), date.getDate());
        const timeStr = date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });

        if (datePart.getTime() === today.getTime()) {
            return `Сегодня в ${timeStr}`;
        } else if (datePart.getTime() === yesterday.getTime()) {
            return `Вчера в ${timeStr}`;
        } else {
            return `${date.toLocaleDateString('ru-RU')} в ${timeStr}`;
        }
    };

    const FormFactorIcon = ({ factor }: { factor?: string }) => {
        if (factor === 'liquid') return <Droplets size={20} strokeWidth={2} style={{ display: 'block' }} />;
        if (factor === 'injection') return <Syringe size={20} strokeWidth={2} style={{ display: 'block' }} />;
        return <Pill size={20} strokeWidth={2} style={{ display: 'block' }} />;
    };

    return (
        <div className="page-container fab-page">
            <div className="max-width-container">
                <div className="safe-area-padding" style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: 'var(--spacing-lg)',
                    minHeight: '40px',
                }}>
                    <h1 className="display-headline" style={{ fontSize: 'var(--text-display)', margin: 0 }}>
                        Лекарства
                    </h1>
                </div>

                {isLoading ? (
                    <SkeletonList
                        count={3}
                        gap={undefined /* use default token gap */}
                        render={() => <MedicationCardSkeleton />}
                    />
                ) : isError && medications.length === 0 ? (
                    <LoadError what="лекарства" onRetry={refetch} />
                ) : medications.length === 0 ? (
                    <EmptyState
                        icon={Pill}
                        title="Здесь будут лекарства питомца"
                        description="Добавьте лекарство, и Petzy напомнит о приёме и покажет остаток"
                        actionLabel="Добавить лекарство"
                        onAction={() => navigate('/medications/new')}
                    />
                ) : (
                    <PullToRefresh
                        onRefresh={async () => {
                            hapticFeedback('medium');
                            await refetch();
                        }}
                        headHeight={48}
                    >
                    <div className="safe-area-padding" style={{
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 'var(--spacing-md)',
                        marginTop: 'var(--spacing-sm)',
                    }}>
                        <PendingIntakesNotice />
                        {orderedMedications.some((m) => (m.course_status ? m.course_status === 'active' : m.is_active) && m.schedule.times.length > 0) && <PushOffNotice />}
                        {orderedMedications.length >= 6 && (
                            <SearchBar placeholder="Найти лекарство" value={search} onChange={setSearch} onClear={() => setSearch('')} />
                        )}
                        {needle && shownMedications.length === 0 && (
                            <div style={{ textAlign: 'center', color: 'var(--app-text-secondary)', padding: 'var(--spacing-lg)' }}>
                                Ничего не найдено по «{search.trim()}»
                            </div>
                        )}
                        {shownMedications.map((med) => (
                            <SwipeableRow
                                key={med._id}
                                itemLabel={med.name}
                                leftAction={{
                                    icon: <Pencil size={20} strokeWidth={2.4} />,
                                    label: 'Изменить',
                                    color: 'var(--app-accent)',
                                    onTrigger: () => navigate(`/medications/${med._id}/edit`),
                                }}
                                rightAction={{
                                    icon: <Trash2 size={20} strokeWidth={2.4} />,
                                    label: 'Удалить',
                                    color: 'var(--app-danger-color)',
                                    onTrigger: () => handleDelete(med),
                                }}
                            >
                            {/* Tap opens the edit form, swipe edits or deletes. */}
                            <Card
                                className="card-soft card-soft--interactive"
                                onClick={() => navigate(`/medications/${med._id}/edit`)}
                                style={{
                                    borderRadius: 'var(--radius-md)',
                                    border: 'none',
                                    padding: 0,
                                    cursor: 'pointer',
                                }}
                            >
                                <div style={{ padding: 'var(--spacing-lg)' }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-md)' }}>
                                    <div style={{ flex: 1, minWidth: 0 }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                        <div>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-sm)', marginBottom: 'var(--spacing-xs)', flexWrap: 'wrap' }}>
                                                <div
                                                    style={{
                                                        width: 36,
                                                        height: 36,
                                                        borderRadius: 12,
                                                        background: 'var(--app-accent-soft)',
                                                        color: 'var(--app-accent-deep)',
                                                        display: 'flex',
                                                        alignItems: 'center',
                                                        justifyContent: 'center',
                                                        flexShrink: 0,
                                                    }}
                                                >
                                                    <FormFactorIcon factor={med.form_factor} />
                                                </div>
                                                <h2 style={{ margin: 0, fontSize: 'var(--text-lg)', fontWeight: 600 }}>{med.name}</h2>
                                                {courseTag(med) && <span className="course-tag">{courseTag(med)}</span>}
                                            </div>
                                            <p style={{ margin: 0, fontSize: 'var(--text-sm)', color: 'var(--app-text-secondary)' }}>
                                                {med.strength ? `${med.strength}` : med.type}
                                                <span style={{ margin: `0 var(--spacing-xs)`, color: 'var(--app-divider-color)' }}>|</span>
                                                По {formatAmount(med.default_dose || 1)} {med.dose_unit || 'шт.'}
                                            </p>
                                        </div>
                                    </div>

                                    <div style={{ marginTop: 'var(--spacing-md)', fontSize: 'var(--text-xs)', color: 'var(--app-text-secondary)', lineHeight: 'var(--line-height-normal)' }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-xs)', marginBottom: 'var(--spacing-sm)' }}>
                                            <ClockCircleOutline />
                                            <span>
                                                {med.schedule.times.length === 0
                                                    ? 'По необходимости'
                                                    : `${med.schedule.days.length === 7 ? 'Ежедневно' : 'В выбранные дни'} в ${med.schedule.times.join(', ')}`}
                                            </span>
                                        </div>

                                        {coursePeriod(med) && (
                                            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-xs)', marginBottom: 'var(--spacing-sm)' }}>
                                                <span>{coursePeriod(med)}</span>
                                            </div>
                                        )}
                                        {med.purpose && (
                                            <div style={{ marginBottom: 'var(--spacing-sm)' }}>
                                                <span>От чего: {med.purpose}</span>
                                            </div>
                                        )}

                                        {med.scheduled_today && med.open_slots_today && (
                                            <div style={{ marginBottom: 'var(--spacing-sm)' }}>
                                                <span>
                                                    {todayProgress(med)}
                                                </span>
                                            </div>
                                        )}

                                        {med.schedule.times.length === 0 && (med.intakes_today ?? 0) > 0 && (
                                            <div style={{ marginBottom: 'var(--spacing-sm)' }}>
                                                <span>Сегодня давали: {med.intakes_today} {pluralRu(med.intakes_today ?? 0, 'раз', 'раза', 'раз')}</span>
                                            </div>
                                        )}

                                        {med.last_taken_at && (
                                            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-xs)', marginBottom: 'var(--spacing-sm)', color: 'var(--app-primary-text)' }}>
                                                <span>Последний приём: {formatRelativeTime(toDeviceClock(med.last_taken_at, med.last_taken_tz).replace(' ', 'T'))}</span>
                                            </div>
                                        )}

                                        {/* Who added this course — hidden when it's the
                                            current user, same convention as HistoryItem's
                                            author chip (single-owner households shouldn't
                                            see their own name everywhere). */}
                                        {med.username && med.username !== currentUsername && (
                                            <button
                                                type="button"
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    navigate(`/users/${med.username}`);
                                                }}
                                                style={{
                                                    display: 'inline-flex',
                                                    alignItems: 'center',
                                                    gap: 'var(--spacing-sm)',
                                                    marginBottom: 'var(--spacing-sm)',
                                                    background: 'none',
                                                    border: 'none',
                                                    padding: 0,
                                                    cursor: 'pointer',
                                                    font: 'inherit',
                                                    color: 'var(--app-text-secondary)',
                                                }}
                                            >
                                                <UserAvatar username={med.username} size={16} />
                                                Добавил(а) {med.username}
                                            </button>
                                        )}

                                    </div>

                                    </div>
                                    {/* Centred on the details, not the whole card: beside the
                                        «Отметить приём» button it would read as the button's. */}
                                    <CardChevron />
                                    </div>
                                    {/* The stock is the width of the whole card, like the buttons below it: «Пополнить» ends where «Дали сейчас» does,
                                        not at the chevron's column. */}
                                        {(() => {
                                            const stock = stockSummary(med);
                                            if (!stock) return null;
                                            const toneColor = stock.tone === 'out'
                                                ? 'var(--app-danger-text)'
                                                : stock.tone === 'low' ? 'var(--app-warning-text)' : 'var(--app-text-primary)';
                                            return (
                                                // Its own controls: a tap here isn't a tap on the card.
                                                <div
                                                    onClick={(e) => e.stopPropagation()}
                                                    style={{
                                                        marginTop: 'var(--spacing-md)',
                                                        display: 'flex',
                                                        alignItems: 'center',
                                                        justifyContent: 'space-between',
                                                        gap: 'var(--spacing-md)',
                                                    }}
                                                >
                                                    <div style={{ minWidth: 0 }}>
                                                        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', columnGap: 'var(--spacing-sm)', fontSize: 'var(--text-sm)', fontWeight: 600, color: toneColor }}>
                                                            <span>{stock.amount}</span>
                                                            {stock.flag && <span>{stock.flag}</span>}
                                                        </div>
                                                        {stock.lasts && (
                                                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--app-text-secondary)', marginTop: 'var(--spacing-2xs)' }}>
                                                                {stock.lasts}
                                                            </div>
                                                        )}
                                                    </div>
                                                    <Button
                                                        size="small"
                                                        fill="outline"
                                                        color="primary"
                                                        onClick={() => openRestock(med)}
                                                        style={{ flexShrink: 0 }}
                                                    >
                                                        Пополнить
                                                    </Button>
                                                </div>
                                            );
                                        })()}
                                    {(med.course_status ? med.course_status === 'active' : med.is_active) && (
                                        // Logging a dose is its own action, not a tap on the card
                                        // (a disabled button's click must not open the form either).
                                        <div style={{ marginTop: 'var(--spacing-xl)' }} onClick={(e) => e.stopPropagation()}>
                                            <Button
                                                block
                                                color="primary"
                                                fill="outline"
                                                onClick={() => logNow(med)}
                                                loading={intakeMutation.isPending && intakeMutation.variables?.id === med._id}
                                                disabled={doneToday(med) || justGiven.includes(med._id)}
                                                aria-label={doneToday(med) ? `${med.name}: на сегодня всё` : `Дали сейчас: ${med.name}`}
                                            >
                                                {doneToday(med) ? 'На сегодня всё' : `Дали сейчас (${formatAmount(med.default_dose || 1)} ${med.dose_unit || ''})`}
                                            </Button>
                                            {!doneToday(med) && (
                                                // The common case is one tap; another time or another amount is a step aside.
                                                <Button
                                                    block
                                                    fill="none"
                                                    onClick={() => handleLogIntake(med)}
                                                    aria-label={`Другое время или доза: ${med.name}`}
                                                    style={{ marginTop: 'var(--spacing-sm)', color: 'var(--app-accent-deep)', background: 'var(--app-accent-soft)' }}
                                                >
                                                    Другое время или доза
                                                </Button>
                                            )}
                                            {doneToday(med) && (
                                                // Every dose of the day is handled, and one more was given (a vet said so, a missed
                                                // one made up): written down on purpose, not through a stale screen.
                                                <Button
                                                    block
                                                    fill="none"
                                                    onClick={() => handleLogIntake(med)}
                                                    aria-label={`Записать дополнительный приём: ${med.name}`}
                                                    style={{ marginTop: 'var(--spacing-sm)', color: 'var(--app-accent-deep)', background: 'var(--app-accent-soft)' }}
                                                >
                                                    Записать дополнительный приём
                                                </Button>
                                            )}
                                        </div>
                                    )}
                                    {(med.course_status ? med.course_status !== 'planned' : true) && (
                                        // Ended or going: the course is finished or taken up again from the list, not only from the bottom of its form.
                                        <div style={{ marginTop: 'var(--spacing-md)', paddingTop: 'var(--spacing-xs)', borderTop: '1px solid var(--app-divider-color)' }} onClick={(e) => e.stopPropagation()}>
                                            <Button
                                                block
                                                fill="none"
                                                onClick={() => void toggleCourse(med)}
                                                aria-label={`${(med.course_status ? med.course_status === 'ended' : !med.is_active) ? 'Возобновить' : 'Завершить'} курс: ${med.name}`}
                                                style={{ color: 'var(--app-accent-deep)' }}
                                            >
                                                {(med.course_status ? med.course_status === 'ended' : !med.is_active) ? 'Возобновить курс' : 'Завершить курс'}
                                            </Button>
                                        </div>
                                    )}
                                </div>
                            </Card>
                            </SwipeableRow>
                        ))}
                        {!needle && endedCount > 0 && endedCount < orderedMedications.length && (
                            <Button block fill="none" onClick={() => setShowEnded((v) => !v)} aria-expanded={showEnded} style={{ color: 'var(--app-text-secondary)' }}>
                                {showEnded ? 'Скрыть завершённые' : `Завершённые курсы: ${endedCount}`}
                            </Button>
                        )}
                    </div>
                    </PullToRefresh>
                )}
            </div>

            {/* The same round «+» as the feed's, the card's and the documents': a medicine is added from the bottom right. */}
            {medications.length > 0 && <Fab label="Добавить лекарство" onClick={() => navigate('/medications/new')} />}

            {/* A sheet from the bottom, as every other form of the app: the thumb reaches the one button that writes. */}
            <Popup
                visible={logIntakeDialog.visible}
                onMaskClick={() => setLogIntakeDialog(prev => ({ ...prev, visible: false }))}
                afterClose={() => setLogIntakeDialog({ visible: false, medication: null, dose: '1', choice: 'now', slot: null, other: null, ago: null })}
                position="bottom"
                bodyStyle={{ background: 'transparent' }}
            >
                <DraggableSheetBody visible={logIntakeDialog.visible} onClose={() => setLogIntakeDialog(prev => ({ ...prev, visible: false }))} maxHeight="90vh" label="Отметить приём">
                    {logIntakeDialog.medication && (
                        <div className="intake">
                            <h2 className="intake__title">Отметить приём</h2>
                            <p className="intake__med">
                                {logIntakeDialog.medication.name}
                                {logIntakeDialog.medication.strength ? `, ${logIntakeDialog.medication.strength}` : ''}
                            </p>

                            <h3 className="intake__label">Сколько дали?</h3>
                            <div className="intake__dose">
                                <Input
                                    value={logIntakeDialog.dose}
                                    type="text"
                                    inputMode="decimal"
                                    aria-label="Сколько дали"
                                    onChange={val => {
                                        if (isAmountDraft(val)) setLogIntakeDialog(prev => ({ ...prev, dose: val }));
                                    }}
                                    className="intake__dose-input"
                                />
                                <span className="intake__unit">{logIntakeDialog.medication.dose_unit || 'шт.'}</span>
                            </div>

                            <h3 className="intake__label">Когда дали?</h3>
                            {/* One question, one row of answers: now, the slot's time, a little while ago, or a time of one's own. */}
                            <ChoiceChips label="Когда дали" flush>
                                <ChoiceChip pressed={logIntakeDialog.choice === 'now'} onClick={() => setLogIntakeDialog(prev => ({ ...prev, choice: 'now', ago: null }))}>
                                    Сейчас
                                </ChoiceChip>
                                {logIntakeDialog.slot && (
                                    <ChoiceChip pressed={logIntakeDialog.choice === 'slot'} onClick={() => setLogIntakeDialog(prev => ({ ...prev, choice: 'slot', ago: null }))}>
                                        {`В ${logIntakeDialog.slot}`}
                                    </ChoiceChip>
                                )}
                                {[
                                    { label: '15 минут назад', when: () => minutesAgo(15) },
                                    { label: 'Час назад', when: () => minutesAgo(60) },
                                    { label: 'Вчера вечером', when: yesterdayEvening },
                                ].map((ago) => (
                                    <ChoiceChip
                                        key={ago.label}
                                        pressed={logIntakeDialog.choice === 'other' && logIntakeDialog.ago === ago.label}
                                        onClick={() => setLogIntakeDialog((prev) => ({ ...prev, choice: 'other', other: ago.when(), ago: ago.label }))}
                                    >
                                        {ago.label}
                                    </ChoiceChip>
                                ))}
                                <ChoiceChip pressed={logIntakeDialog.choice === 'other' && !logIntakeDialog.ago} onClick={() => setWhenPickerVisible(true)}>
                                    {logIntakeDialog.choice === 'other' && !logIntakeDialog.ago && logIntakeDialog.other ? whenLabel(logIntakeDialog.other) : 'Выбрать время'}
                                </ChoiceChip>
                            </ChoiceChips>

                            <div className="intake__actions">
                                <Button block color="primary" size="large" onClick={confirmLogIntake}>
                                    Записать
                                </Button>
                                <Button block fill="none" onClick={() => setLogIntakeDialog(prev => ({ ...prev, visible: false }))}>
                                    Отмена
                                </Button>
                                {/* Last, and apart from «Записать»: a skip closes the dose and stops its reminder.
                                    A course taken when needed has no dose to skip. */}
                                {logIntakeDialog.medication.schedule.times.length > 0 && (
                                    <div className="intake__skip">
                                        <Button block fill="none" onClick={skipIntake} style={{ color: 'var(--app-text-secondary)' }}>
                                            Пропустить приём
                                        </Button>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}
                </DraggableSheetBody>
            </Popup>

            <IntakeTimePicker
                visible={whenPickerVisible}
                value={logIntakeDialog.other ?? nowWhen()}
                onClose={() => setWhenPickerVisible(false)}
                onConfirm={(when) => setLogIntakeDialog(prev => ({ ...prev, choice: 'other', other: when, ago: null }))}
            />

            <Dialog
                visible={!!restock.medication}
                title="Пополнить остаток"
                content={
                    restock.medication && (
                        <div style={{ textAlign: 'center' }}>
                            <div style={{ marginBottom: 'var(--spacing-lg)', fontSize: 'var(--text-sm)', color: 'var(--app-text-secondary)' }}>
                                {restock.medication.name}: сейчас {formatAmount(Math.max(0, restock.medication.inventory_current ?? 0))} {restock.medication.dose_unit || 'доз'}
                            </div>
                            <div style={{ fontSize: 'var(--text-lg)', fontWeight: 600, marginBottom: 'var(--spacing-lg)' }}>
                                Сколько купили?
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px' }}>
                                <Input
                                    value={restock.amount}
                                    type="text"
                                    inputMode="decimal"
                                    placeholder="0"
                                    autoFocus
                                    onChange={(val) => {
                                        if (isAmountDraft(val)) setRestock((prev) => ({ ...prev, amount: val }));
                                    }}
                                    style={{
                                        '--text-align': 'center',
                                        width: '80px',
                                        fontSize: 'var(--text-lg)',
                                        border: '1px solid var(--app-border-color)',
                                        borderRadius: 'var(--radius-sm)',
                                        padding: 'var(--spacing-xs)'
                                    }}
                                />
                                <span style={{ fontSize: 'var(--text-md)', fontWeight: 500 }}>
                                    {restock.medication.dose_unit || 'доз'}
                                </span>
                            </div>
                        </div>
                    )
                }
                onClose={() => setRestock((prev) => ({ ...prev, medication: null }))}
                actions={[
                    { key: 'confirm', text: 'Добавить', bold: true, onClick: confirmRestock },
                    { key: 'cancel', text: 'Отмена', onClick: () => setRestock((prev) => ({ ...prev, medication: null })) },
                ]}
            />

            <Dialog
                visible={deleteDialog.visible}
                title="Удаление лекарства"
                content={
                    deleteDialog.medication && (
                        <span>{medicationDeleteText(deleteDialog.medication.name)}</span>
                    )
                }
                onClose={() => setDeleteDialog(prev => ({ ...prev, visible: false }))}
                afterClose={() => setDeleteDialog({ visible: false, medication: null })}
                actions={[
                    {
                        key: 'delete',
                        text: 'Удалить',
                        danger: true,
                        onClick: () => {
                            if (deleteDialog.medication) {
                                deleteMedicationWithUndo(deleteDialog.medication, queryClient);
                            }
                            setDeleteDialog(prev => ({ ...prev, visible: false }));
                        }
                    },
                    {
                        key: 'cancel',
                        text: 'Отмена',
                        onClick: () => setDeleteDialog(prev => ({ ...prev, visible: false }))
                    },
                ]}
            />
        </div>
    );
}
