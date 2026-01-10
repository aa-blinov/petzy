import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, Button, Toast } from 'antd-mobile';
import { ClockCircleOutline, CheckOutline, ExclamationCircleOutline } from 'antd-mobile-icons';
import { medicationsService, type UpcomingDose } from '../services/medications.service';
import { usePet } from '../hooks/usePet';

export function NextDoseWidget() {
    const { selectedPetId } = usePet();
    const queryClient = useQueryClient();

    const { data: upcoming = [], isLoading } = useQuery({
        queryKey: ['medications', 'upcoming', selectedPetId],
        queryFn: () => {
            const now = new Date();
            // ISO string format: YYYY-MM-DDTHH:mm:ss.sssZ
            // We want to pass the local time representation or just the ISO string.
            // Backend expects ISO-like usage or YYYY-MM-DD HH:MM.
            // Let's pass ISO string, backend handles checking T.
            return medicationsService.getUpcoming(selectedPetId!, now.toISOString());
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
            Toast.show({ icon: 'success', content: 'Принято!' });
        }
    });

    if (isLoading || upcoming.length === 0) return null;

    // For the widget, we only show the VERY next dose (or multiple if they are at the same time)
    const nextDose = upcoming[0];

    return (
        <Card
            style={{
                marginBottom: 'var(--spacing-lg)',
                borderRadius: 'var(--radius-lg)',
                background: 'var(--app-blue-gradient)',
                color: 'var(--color-white)',
                border: 'none'
            }}
        >
            <div style={{ padding: 'var(--spacing-lg)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div>
                        <div style={{ fontSize: 'var(--text-xs)', opacity: 0.9, marginBottom: 'var(--spacing-xs)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                            Следующий прием
                        </div>
                        <h3 style={{ margin: 0, fontSize: 'var(--text-xl)', fontWeight: 700 }}>{nextDose.name}</h3>
                        <div style={{ fontSize: 'var(--text-sm)', opacity: 0.9, marginTop: '2px' }}>
                            {nextDose.type} • {nextDose.time}
                        </div>
                    </div>
                    <div style={{ backgroundColor: 'var(--app-white-20)', padding: 'var(--spacing-sm)', borderRadius: 'var(--radius-md)' }}>
                        <ClockCircleOutline style={{ fontSize: 'var(--spacing-xl)' }} />
                    </div>
                </div>

                {nextDose.inventory_warning && (
                    <div style={{
                        marginTop: 'var(--spacing-md)',
                        backgroundColor: 'var(--app-black-20)',
                        padding: 'var(--spacing-sm)',
                        borderRadius: 'var(--radius-sm)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 'var(--spacing-sm)',
                        fontSize: 'var(--text-xs)'
                    }}>
                        <ExclamationCircleOutline />
                        <span>Мало лекарства в остатке!</span>
                    </div>
                )}

                <div style={{ marginTop: 'var(--spacing-lg)' }}>
                    <Button
                        block
                        shape="rounded"
                        style={{
                            '--background-color': 'var(--color-white)',
                            '--text-color': 'var(--app-primary-color)',
                            fontWeight: 600
                        } as React.CSSProperties}
                        onClick={() => intakeMutation.mutate(nextDose)}
                        loading={intakeMutation.isPending}
                    >
                        <CheckOutline /> Принять сейчас
                    </Button>
                </div>
            </div>
        </Card>
    );
}
