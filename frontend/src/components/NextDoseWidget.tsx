import { useEffect, useMemo, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { formatDate, formatTime } from '../utils/dateUtils';
import { refreshAfterIntake } from '../utils/intakeViews';
import { showUndo } from '../utils/undo';
import { INTAKE_UNDO_MS } from '../utils/stock';
import { showToast } from '../utils/toast';
import { getApiErrorMessage } from '../utils/apiError';
import { useNavigate } from 'react-router-dom';
import { Button } from 'antd-mobile';
import { Check, Pill, TriangleAlert } from 'lucide-react';
import { medicationsListQuery, medicationsService, type UpcomingDose } from '../services/medications.service';
import { useAuth } from '../hooks/useAuth';
import { IntakeDeclined, logIntakeAsking } from '../utils/duplicateIntake';
import { usePet } from '../hooks/usePet';
import { toDeviceClock } from '../utils/timezone';
import { useHiddenRecords } from '../utils/deferredDelete';

/**
 * Today's next dose, on the feed. Only today's: marking a dose for a day
 * that hasn't come yet («Отметить заранее», offered once today's were all
 * given) let one tap after another log tomorrow's, then the next day's,
 * into the diary, which no medication app does. Once today is done the
 * widget steps aside; the reminder brings the next dose back in time.
 *
 * A stray tap is undone from the bar that follows («Отменить»), not
 * guarded by a question before every dose. A due dose can also be
 * skipped on purpose (a vet said to, the pet refused it): the slot is
 * handled and the reminder stops, but nothing leaves the stock.
 */
const DUE_WINDOW_MINUTES = 30;

/** Minutes from now to the dose's own moment; negative once it has passed (a dose of last evening, long). */
function minutesUntilDose(dose: UpcomingDose, now = new Date()): number {
    return Math.round((new Date(`${dose.date}T${dose.time}:00`).getTime() - now.getTime()) / 60000);
}

/** «Принять» now, «Уже дали в 08:00» at the slot, or «Пропустить». */
type IntakeKind = 'now' | 'scheduled' | 'skip';

export function NextDoseWidget() {
    const { selectedPetId, selectedPetName } = usePet();
    const queryClient = useQueryClient();
    const navigate = useNavigate();

    const hiddenMedications = useHiddenRecords();
    const { data: allUpcoming = [], isLoading, isFetching } = useQuery({
        queryKey: ['medications', 'upcoming', selectedPetId],
        queryFn: () => {
            // The client's own wall clock, not toISOString(): that emits
            // UTC, and the backend treats this value as local — it takes
            // the weekday from it, bounds "today's intakes" by it, and
            // compares it against schedule times like "08:00" that are
            // local. Sending UTC shifted every judgement by the viewer's
            // offset, so a dose an hour overdue still read as upcoming
            // (at UTC+5, a five-hour blind window).
            const now = new Date();
            return medicationsService.getUpcoming(
                selectedPetId!,
                `${formatDate(now)}T${formatTime(now)}:00`,
            );
        },
        enabled: !!selectedPetId,
        // Another person may have marked this dose: looked at again every half minute and whenever the app comes back to
        // the front, not left to show a dose that is already given.
        refetchInterval: 30000,
        refetchOnWindowFocus: true,
        // Always looked at again on return: the app-wide thirty seconds of «fresh» would let a given dose stay on the card.
        staleTime: 0,
    });
    // A course deleted a moment ago, «Отменить» still on offer, has no dose on the card.
    const upcoming = useMemo(() => allUpcoming.filter((d) => !hiddenMedications.has(d.medication_id)), [allUpcoming, hiddenMedications]);

    const intakeMutation = useMutation({
        onMutate: () => { lastOwnMark.current = Date.now(); },
        mutationFn: ({ dose, kind }: { dose: UpcomingDose; kind: IntakeKind }) => {
            // No dose_taken: the backend uses the course's own dose. A
            // hard-coded 1 took a whole tablet off a half-tablet course.
            // «Принять» is logged at the moment it's given, not at the
            // scheduled time: «Дать раньше» at 14:00 for 20:00 is a 14:00
            // intake. «Уже дали в 08:00» is for a dose given on time and
            // marked later; a skip sits at its slot.
            const now = new Date();
            const nowDate = formatDate(now);
            const nowTime = formatTime(now);
            // The slot the dose is for goes with it: «Принять сейчас» at 14:30 for the 08:00 dose closes the 08:00 one,
            // not the nearest, and a dose of last evening given after midnight closes that evening.
            const slot = { slot_date: dose.date, slot_time: dose.time };
            if (kind === 'now')
              return logIntakeAsking(dose.medication_id, dose.name, { date: nowDate, time: nowTime, ...slot }, selectedPetName ?? undefined);
            const slotIsPast = `${dose.date} ${dose.time}` <= `${nowDate} ${nowTime}`;
            const at = slotIsPast ? { date: dose.date, time: dose.time } : { date: nowDate, time: nowTime };
            return logIntakeAsking(dose.medication_id, dose.name, { ...at, ...slot, skipped: kind === 'skip' }, selectedPetName ?? undefined);
        },
        onSuccess: ({ id, ran_out, queued }, { dose, kind }) => {
            if (queued) {
                showToast.info('Нет связи. Отметка сохранена на телефоне и отправится сама');
                return;
            }
            refreshAfterIntake(queryClient);
            const message =
                kind === 'skip'
                    ? `${dose.name}: приём пропущен`
                    : ran_out
                        ? `${dose.name}: принято, лекарство закончилось. Пополните остаток`
                        : kind === 'scheduled'
                            ? `${dose.name}: отмечено, дали в ${dose.time}${dose.carried_over ? ' вчера' : ''}`
                            : -minutesUntilDose(dose) > DUE_WINDOW_MINUTES
                                ? `${dose.name}: принято, закрыт приём в ${dose.time}${dose.carried_over ? ' вчера' : ''}`
                                : `${dose.name}: приём отмечен`;
            // Ten seconds: a dose is marked with a thumb, and read back a moment later. The «лекарство закончилось» is in the
            // same message: a second one on top of it took the «Отменить» away.
            showUndo({
                duration: INTAKE_UNDO_MS,
                message,
                onUndo: async () => {
                    await medicationsService.deleteIntake(id);
                    await refreshAfterIntake(queryClient);
                },
            });
        },
        onError: (err: unknown, { kind }) => {
            if (err instanceof IntakeDeclined) return;
            showToast.failure(getApiErrorMessage(err, kind === 'skip' ? 'Не удалось пропустить приём' : 'Не удалось отметить приём'));
        }
    });

    // The dose on the card was marked by someone else while it was open: it goes away, and the person is told who and
    // when, instead of watching a card vanish. (A dose marked from this phone says so itself, in its own bar.)
    const shown = useRef<UpcomingDose | null>(null);
    const lastOwnMark = useRef(0);
    const { username } = useAuth();
    useEffect(() => {
        const was = shown.current;
        const stillThere = upcoming.some((d) => d.medication_id === was?.medication_id && d.date === was?.date && d.time === was?.time);
        const next = upcoming.filter((d) => d.date === formatDate(new Date()) || d.carried_over)[0] ?? null;
        if (was && !stillThere && Date.now() - lastOwnMark.current > 20_000 && selectedPetId) {
            void queryClient.fetchQuery({ ...medicationsListQuery(selectedPetId), staleTime: 0 }).then((meds) => {
                const med = meds.find((m) => m._id === was.medication_id);
                if (med?.last_taken_by && med.last_taken_by !== username && med.last_taken_at) {
                    showToast.info(`${was.name}: приём в ${toDeviceClock(med.last_taken_at, med.last_taken_tz).slice(11, 16)} уже отметил ${med.last_taken_by}`);
                }
            }).catch(() => undefined);
        }
        shown.current = next;
    }, [upcoming, queryClient, selectedPetId, username]);

    // The courses: to tell «everything is given for today» from «nothing is scheduled», which look alike when the card is gone.
    const courses = useQuery({ ...medicationsListQuery(selectedPetId ?? ''), enabled: !!selectedPetId });

    const today = formatDate(new Date());
    // Today's, and last evening's that nobody marked: a dose forgotten at 23:30 is still there at 00:10.
    const todays = upcoming.filter((dose) => dose.date === today || dose.carried_over);
    if (isLoading) return null;
    if (todays.length === 0) {
        const scheduled = (courses.data ?? []).filter((m) => (m.course_status ? m.course_status === 'active' : m.is_active) && m.scheduled_today);
        if (scheduled.length === 0 || scheduled.some((m) => (m.open_slots_today?.length ?? 0) > 0)) return null;
        return (
            <div className="card-soft" role="status" style={{ marginBottom: 'var(--spacing-lg)', padding: 'var(--spacing-md) var(--spacing-lg)', display: 'flex', alignItems: 'center', gap: 'var(--spacing-sm)', color: 'var(--app-success-text)', fontWeight: 600 }}>
                <Check size={18} strokeWidth={2.4} aria-hidden style={{ flexShrink: 0 }} />
                Все приёмы на сегодня отмечены
            </div>
        );
    }

    // The next of today's doses: an overdue one first (the list is in time order).
    const nextDose = todays[0];
    const sameTimeAsNext = todays.filter((d) => d !== nextDose && d.date === nextDose.date && d.time === nextDose.time).length;
    // Due from half an hour before its time: at 07:50 an 08:00 dose is
    // «Пора дать лекарство», not «Дать раньше».
    const minutesUntil = minutesUntilDose(nextDose);
    const due = nextDose.is_overdue || minutesUntil <= DUE_WINDOW_MINUTES;
    const busy = intakeMutation.isPending || isFetching;
    const pendingKind = intakeMutation.isPending ? intakeMutation.variables?.kind : undefined;

    return (
        <div
            className="card-soft"
            style={{
                marginBottom: 'var(--spacing-lg)',
                padding: 'var(--spacing-lg)',
            }}
        >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 'var(--spacing-md)' }}>
                <div style={{ display: 'flex', gap: 'var(--spacing-md)', minWidth: 0 }}>
                    {/* Same badge shape/colors as the medication cards on the
                        Лекарства tab — the point is to read as "this is a
                        medication" at a glance, the same way that page does. */}
                    <div
                        aria-hidden
                        style={{
                            width: 40,
                            height: 40,
                            borderRadius: 12,
                            background: 'var(--app-accent-soft)',
                            color: 'var(--app-accent-deep)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            flexShrink: 0,
                        }}
                    >
                        <Pill size={20} strokeWidth={2} style={{ display: 'block' }} />
                    </div>
                    <div style={{ minWidth: 0 }}>
                        <div style={{ fontSize: 'var(--text-xs)', color: due ? 'var(--app-accent-deep)' : 'var(--app-text-secondary)', fontWeight: due ? 700 : 400, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                            {due ? 'Пора дать лекарство' : 'Следующий приём'}
                        </div>
                        <h2
                            className="clamp-2"
                            style={{
                                margin: 'var(--spacing-2xs) 0 0',
                                fontSize: 'var(--text-lg)',
                                fontWeight: 700,
                                color: 'var(--app-text-primary)',
                                overflowWrap: 'anywhere',
                            }}
                        >
                            {nextDose.name}
                        </h2>
                        <div style={{ fontSize: 'var(--text-sm)', color: 'var(--app-text-secondary)', marginTop: 'var(--spacing-2xs)' }}>
                            {nextDose.carried_over
                                ? `вчера в ${nextDose.time}, не отмечено`
                                : due ? `по расписанию в ${nextDose.time}` : `сегодня в ${nextDose.time}`}
                        </div>
                        {todays.length > 1 && (
                            // One card for one dose: what else is waiting is said, not left to appear after the first is marked.
                            <div style={{ fontSize: 'var(--text-sm)', color: 'var(--app-text-secondary)', marginTop: 'var(--spacing-2xs)' }}>
                                {sameTimeAsNext > 0
                                    ? `ещё ${sameTimeAsNext} ${sameTimeAsNext === 1 ? 'лекарство' : 'лекарства'} в это же время, всего сегодня осталось ${todays.length}`
                                    : `сегодня осталось приёмов: ${todays.length}`}
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {nextDose.inventory_warning && (
                <div style={{
                    marginTop: 'var(--spacing-md)',
                    backgroundColor: 'var(--app-danger-soft)',
                    color: 'var(--app-danger-text)',
                    padding: 'var(--spacing-sm) var(--spacing-md)',
                    borderRadius: 'var(--radius-sm)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--spacing-sm)',
                    fontSize: 'var(--text-xs)',
                }}>
                    <TriangleAlert size={16} strokeWidth={2} style={{ display: 'block', flexShrink: 0 }} />
                    <span style={{ flex: 1 }}>{nextDose.name} заканчивается, пора купить</span>
                    <button
                        type="button"
                        className="touch-target"
                        onClick={() => navigate(`/medications?restock=${nextDose.medication_id}`)}
                        style={{ border: 'none', background: 'transparent', color: 'inherit', font: 'inherit', fontWeight: 600, textDecoration: 'underline', padding: 'var(--spacing-xs)' }}
                    >
                        Пополнить
                    </button>
                </div>
            )}

            {/* The same three levels as the actions of a course on the Medicines screen: the main button, a tonal one for the step
                aside, and under a hairline a quiet text button for the decision that closes the dose. */}
            <div style={{ marginTop: 'var(--spacing-lg)', display: 'flex', flexDirection: 'column', gap: 'var(--spacing-sm)' }}>
                <Button
                    block
                    color="primary"
                    // Due: the main action. Later today: possible, but not
                    // what the card is asking for, so it doesn't shout.
                    fill={due ? 'solid' : 'outline'}
                    onClick={() => intakeMutation.mutate({ dose: nextDose, kind: 'now' })}
                    loading={pendingKind === 'now'}
                    // Once the log request succeeds, the invalidated query
                    // needs its own refetch round-trip before `upcoming`
                    // reflects the new state — without this, that gap let a
                    // second tap (or, on a slower connection, several) log
                    // the same dose again before the button had any visible
                    // reason to stop offering it.
                    disabled={busy}
                >
                    Дали сейчас
                </Button>
                {minutesUntil < 0 && (
                    // The slot has passed: whoever gave the dose on time and marks it only now puts it where it belongs.
                    <Button
                        fill="none"
                        block
                        style={{ color: 'var(--app-accent-deep)', background: 'var(--app-accent-soft)' }}
                        onClick={() => intakeMutation.mutate({ dose: nextDose, kind: 'scheduled' })}
                        loading={pendingKind === 'scheduled'}
                        disabled={busy}
                    >
                        Дали вовремя, в {nextDose.time}{nextDose.carried_over ? ' вчера' : ''}
                    </Button>
                )}
                {due && (
                    // Apart from the buttons above and quiet: a skip closes the dose and stops its reminder, and a
                    // thumb in a hurry should not land on it.
                    <div style={{ marginTop: 'var(--spacing-xs)', paddingTop: 'var(--spacing-xs)', borderTop: '1px solid var(--app-divider-color)' }}>
                        <Button
                            fill="none"
                            block
                            style={{ color: 'var(--app-text-secondary)' }}
                            onClick={() => intakeMutation.mutate({ dose: nextDose, kind: 'skip' })}
                            loading={pendingKind === 'skip'}
                            disabled={busy}
                        >
                            Пропустить приём
                        </Button>
                    </div>
                )}
            </div>
        </div>
    );
}
