import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { formatDate, formatTime } from '../utils/dateUtils';
import { MONTHS_GENITIVE } from '../utils/relativeTime';
import { showToast } from '../utils/toast';
import { getApiErrorMessage } from '../utils/apiError';
import { Button } from 'antd-mobile';
import { Pill, TriangleAlert } from 'lucide-react';
import { medicationsService, type UpcomingDose } from '../services/medications.service';
import { usePet } from '../hooks/usePet';

// The backend looks ahead up to a week once today's doses are all given,
// so "the next dose" can land on a different day — without saying which,
// a dose due tomorrow read exactly like one due right now, and "Принять
// сейчас" on it would log an early, wrong-dated intake.
function describeDoseDay(doseDateStr: string, now: Date): string | null {
    const [y, m, d] = doseDateStr.split('-').map(Number);
    const doseDay = new Date(y, m - 1, d).getTime();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const daysAhead = Math.round((doseDay - today) / 86_400_000);

    if (daysAhead <= 0) return null;
    if (daysAhead === 1) return 'завтра';
    return `${d} ${MONTHS_GENITIVE[m - 1]}`;
}

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
        mutationFn: (dose: UpcomingDose) => {
            return medicationsService.logIntake(dose.medication_id, {
                date: dose.date,
                time: dose.time,
                dose_taken: 1, // Default
            });
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['medications'] });
            showToast.success('Принято!');
        },
        onError: (err: unknown) => {
            showToast.failure(getApiErrorMessage(err, 'Не удалось отметить приём'));
        }
    });

    if (isLoading || upcoming.length === 0) return null;

    // For the widget, we only show the VERY next dose (or multiple if they are at the same time)
    const nextDose = upcoming[0];
    const doseDay = describeDoseDay(nextDose.date, new Date());

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
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--app-text-secondary)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                            Приём лекарства
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
                            {doseDay ? `${doseDay}, ${nextDose.time}` : nextDose.time}
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
                    <span>Мало лекарства в остатке!</span>
                </div>
            )}

            <div style={{ marginTop: 'var(--spacing-lg)' }}>
                <Button
                    block
                    color="primary"
                    shape="rounded"
                    style={{ fontWeight: 600 }}
                    onClick={() => intakeMutation.mutate(nextDose)}
                    loading={intakeMutation.isPending}
                    // Once the log request succeeds, the invalidated query
                    // needs its own refetch round-trip before `upcoming`
                    // reflects the new state — without this, that gap let a
                    // second tap (or, on a slower connection, several) log
                    // the same dose again before the button had any visible
                    // reason to stop offering it.
                    disabled={isFetching}
                >
                    {doseDay ? 'Отметить заранее' : 'Принять сейчас'}
                </Button>
            </div>
        </div>
    );
}
