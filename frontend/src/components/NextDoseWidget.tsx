import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { formatDate, formatTime } from '../utils/dateUtils';
import { refreshAfterIntake } from '../utils/intakeViews';
import { showUndo } from '../utils/undo';
import { showToast } from '../utils/toast';
import { getApiErrorMessage } from '../utils/apiError';
import { RAN_OUT_MESSAGE } from '../utils/stock';
import { Button } from 'antd-mobile';
import { Pill, TriangleAlert } from 'lucide-react';
import { medicationsService, type UpcomingDose } from '../services/medications.service';
import { usePet } from '../hooks/usePet';

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

/** «Принять» now, «Уже дали в 08:00» at the slot, or «Пропустить». */
type IntakeKind = 'now' | 'scheduled' | 'skip';

export function NextDoseWidget() {
    const { selectedPetId } = usePet();
    const queryClient = useQueryClient();

    const { data: upcoming = [], isLoading, isFetching } = useQuery({
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
        refetchInterval: 60000, // Refresh every minute
    });

    const intakeMutation = useMutation({
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
            if (kind === 'now') return medicationsService.logIntake(dose.medication_id, { date: nowDate, time: nowTime });
            const slotIsPast = `${dose.date} ${dose.time}` <= `${nowDate} ${nowTime}`;
            const at = slotIsPast ? { date: dose.date, time: dose.time } : { date: nowDate, time: nowTime };
            return medicationsService.logIntake(dose.medication_id, { ...at, skipped: kind === 'skip' });
        },
        onSuccess: ({ id, ran_out }, { dose, kind }) => {
            refreshAfterIntake(queryClient);
            const message =
                kind === 'skip'
                    ? `${dose.name}: приём пропущен`
                    : ran_out
                        ? `${dose.name}: принято, лекарство закончилось`
                        : kind === 'scheduled'
                            ? `${dose.name}: отмечено, дали в ${dose.time}`
                            : `${dose.name}: приём отмечен`;
            showUndo({
                message,
                onUndo: async () => {
                    await medicationsService.deleteIntake(id);
                    await refreshAfterIntake(queryClient);
                },
            });
            if (ran_out && kind !== 'skip') showToast.info(RAN_OUT_MESSAGE, { duration: 3500 });
        },
        onError: (err: unknown, { kind }) => {
            showToast.failure(getApiErrorMessage(err, kind === 'skip' ? 'Не удалось пропустить приём' : 'Не удалось отметить приём'));
        }
    });

    const today = formatDate(new Date());
    const todays = upcoming.filter((dose) => dose.date === today);
    if (isLoading || todays.length === 0) return null;

    // The next of today's doses: an overdue one first (the list is in time order).
    const nextDose = todays[0];
    // Due from half an hour before its time: at 07:50 an 08:00 dose is
    // «Пора дать лекарство», not «Дать раньше».
    const [h, m] = nextDose.time.split(':').map(Number);
    const now = new Date();
    const minutesUntil = h * 60 + m - (now.getHours() * 60 + now.getMinutes());
    const due = nextDose.is_overdue || minutesUntil <= DUE_WINDOW_MINUTES;
    // Well past its time the dose may have been given on time and not
    // marked: then «Уже дали в 08:00» puts it where it belongs.
    const late = -minutesUntil > DUE_WINDOW_MINUTES;
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
                            style={{
                                margin: '2px 0 0',
                                fontSize: 'var(--text-lg)',
                                fontWeight: 700,
                                color: 'var(--app-text-primary)',
                                whiteSpace: 'nowrap',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                            }}
                        >
                            {nextDose.name}
                        </h2>
                        <div style={{ fontSize: 'var(--text-sm)', color: 'var(--app-text-secondary)', marginTop: '2px' }}>
                            {due ? `по расписанию в ${nextDose.time}` : `сегодня в ${nextDose.time}`}
                        </div>
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
                    <span>Лекарство заканчивается, пора купить</span>
                </div>
            )}

            <div style={{ marginTop: 'var(--spacing-lg)', display: 'flex', flexDirection: 'column', gap: 'var(--spacing-xs)' }}>
                <Button
                    block
                    color="primary"
                    // Due: the main action. Later today: possible, but not
                    // what the card is asking for, so it doesn't shout.
                    fill={due ? 'solid' : 'outline'}
                    shape="rounded"
                    style={{ fontWeight: 600 }}
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
                    {!due ? 'Дать раньше' : late ? 'Принять сейчас' : 'Принять'}
                </Button>
                {due && (
                    <div style={{ display: 'flex', gap: 'var(--spacing-xs)' }}>
                        {late && (
                            <Button
                                fill="none"
                                color="primary"
                                size="small"
                                style={{ flex: 1, minHeight: 40, fontWeight: 600 }}
                                onClick={() => intakeMutation.mutate({ dose: nextDose, kind: 'scheduled' })}
                                loading={pendingKind === 'scheduled'}
                                disabled={busy}
                            >
                                Уже дали в {nextDose.time}
                            </Button>
                        )}
                        <Button
                            fill="none"
                            size="small"
                            style={{ flex: 1, minHeight: 40, color: 'var(--app-text-secondary)' }}
                            onClick={() => intakeMutation.mutate({ dose: nextDose, kind: 'skip' })}
                            loading={pendingKind === 'skip'}
                            disabled={busy}
                        >
                            Пропустить
                        </Button>
                    </div>
                )}
            </div>
        </div>
    );
}
