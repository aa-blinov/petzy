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
        queryFn: () => medicationsService.getUpcoming(selectedPetId!),
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
                marginBottom: '16px',
                borderRadius: '16px',
                background: 'linear-gradient(135deg, var(--adm-color-primary) 0%, #4a90e2 100%)',
                color: '#ffffff',
                border: 'none'
            }}
        >
            <div style={{ padding: '16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div>
                        <div style={{ fontSize: '12px', opacity: 0.9, marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                            Следующий прием
                        </div>
                        <h3 style={{ margin: 0, fontSize: '20px', fontWeight: 700 }}>{nextDose.name}</h3>
                        <div style={{ fontSize: '14px', opacity: 0.9, marginTop: '2px' }}>
                            {nextDose.type} • {nextDose.time}
                        </div>
                    </div>
                    <div style={{ backgroundColor: 'rgba(255,255,255,0.2)', padding: '8px', borderRadius: '12px' }}>
                        <ClockCircleOutline style={{ fontSize: '24px' }} />
                    </div>
                </div>

                {nextDose.inventory_warning && (
                    <div style={{
                        marginTop: '12px',
                        backgroundColor: 'rgba(255, 100, 100, 0.3)',
                        padding: '8px',
                        borderRadius: '8px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        fontSize: '12px'
                    }}>
                        <ExclamationCircleOutline />
                        <span>Мало лекарства в остатке!</span>
                    </div>
                )}

                <div style={{ marginTop: '16px' }}>
                    <Button
                        block
                        shape="rounded"
                        style={{
                            '--background-color': '#ffffff',
                            '--text-color': 'var(--adm-color-primary)',
                            fontWeight: 600
                        }}
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
