import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, Card, Empty, ProgressBar, Toast, Tag, Dialog } from 'antd-mobile';
import { AddOutline, EditSOutline, DeleteOutline, ClockCircleOutline } from 'antd-mobile-icons';
import { useNavigate } from 'react-router-dom';
import { medicationsService, type Medication } from '../services/medications.service';
import { usePet } from '../hooks/usePet';
import { LoadingSpinner } from '../components/LoadingSpinner';

export function MedicationsList() {
    const { selectedPetId } = usePet();
    const navigate = useNavigate();
    const queryClient = useQueryClient();

    const { data: medications = [], isLoading } = useQuery({
        queryKey: ['medications', selectedPetId],
        queryFn: () => medicationsService.getList(selectedPetId!),
        enabled: !!selectedPetId,
    });

    const intakeMutation = useMutation({
        mutationFn: ({ id, dose }: { id: string; dose: number }) => {
            const now = new Date();
            return medicationsService.logIntake(id, {
                date: now.toISOString().split('T')[0],
                time: now.toTimeString().split(' ')[0].substring(0, 5),
                dose_taken: dose,
            });
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['medications'] });
            queryClient.invalidateQueries({ queryKey: ['pets'] }); // Pet might have inventory warning
            Toast.show({
                icon: 'success',
                content: 'Прием отмечен',
                duration: 2000
            });
        },
        onError: (err: any) => {
            Toast.show({
                icon: 'fail',
                content: err?.response?.data?.error || 'Ошибка при сохранении'
            });
        }
    });

    const deleteMutation = useMutation({
        mutationFn: (id: string) => medicationsService.delete(id),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['medications'] });
            Toast.show({ icon: 'success', content: 'Курс удален' });
        }
    });

    const handleDelete = (med: Medication) => {
        Dialog.confirm({
            content: `Удалить курс "${med.name}" и всю его историю?`,
            onConfirm: () => deleteMutation.mutate(med._id),
        });
    };

    const handleLogIntake = (med: Medication) => {
        intakeMutation.mutate({ id: med._id, dose: 1 }); // Default to 1 dose
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

    if (isLoading) return <LoadingSpinner />;

    return (
        <div style={{
            minHeight: '100vh',
            paddingTop: 'calc(env(safe-area-inset-top) + 88px)',
            paddingBottom: 'calc(env(safe-area-inset-bottom) + 80px)',
            backgroundColor: 'var(--app-page-background)',
            color: 'var(--app-text-color)'
        }}>
            <div style={{ maxWidth: '800px', margin: '0 auto', padding: '0 16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                    <h2 style={{ margin: 0, fontSize: '24px', fontWeight: 600 }}>Прием препаратов</h2>
                    <Button
                        color="primary"
                        fill="solid"
                        onClick={() => navigate('/medications/new')}
                        style={{
                            borderRadius: '12px',
                            fontWeight: 500,
                            padding: '8px 16px',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px'
                        }}
                    >
                        <AddOutline style={{ fontSize: '18px' }} /> Добавить
                    </Button>
                </div>

                {medications.length === 0 ? (
                    <Card style={{ padding: '32px 0', textAlign: 'center' }}>
                        <Empty description="Нет назначенных лекарств" />
                    </Card>
                ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                        {medications.map(med => (
                            <Card key={med._id} style={{ borderRadius: '12px', boxShadow: '0 2px 8px rgba(0,0,0,0.05)' }}>
                                <div style={{ padding: '16px' }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                        <div>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px', flexWrap: 'wrap' }}>
                                                <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 600 }}>{med.name}</h3>
                                                {!med.is_active && <Tag color="default">Архив</Tag>}
                                                {med.is_active && (med.intakes_today || 0) >= med.schedule.times.length && (
                                                    <Tag color="success">
                                                        На сегодня всё
                                                    </Tag>
                                                )}
                                            </div>
                                            <p style={{ margin: 0, fontSize: '14px', color: 'var(--app-text-secondary)' }}>
                                                {med.type} {med.dosage && `• ${med.dosage} ${med.unit || ''}`}
                                            </p>
                                        </div>
                                        <div style={{ display: 'flex', gap: '8px' }}>
                                            <Button
                                                size="mini"
                                                fill="outline"
                                                onClick={() => navigate(`/medications/${med._id}/edit`)}
                                            >
                                                <EditSOutline style={{ fontSize: '18px' }} />
                                            </Button>
                                            <Button
                                                size="mini"
                                                fill="outline"
                                                color="danger"
                                                onClick={() => handleDelete(med)}
                                            >
                                                <DeleteOutline style={{ fontSize: '18px' }} />
                                            </Button>
                                        </div>
                                    </div>

                                    <div style={{ marginTop: '12px', fontSize: '13px', color: 'var(--app-text-secondary)' }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
                                            <ClockCircleOutline />
                                            <span>
                                                {med.schedule.days.length === 7 ? 'Ежедневно' : 'В выбранные дни'} в {med.schedule.times.join(', ')}
                                            </span>
                                        </div>

                                        {med.last_taken_at && (
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px', color: 'var(--adm-color-primary)' }}>
                                                <span>Последний прием: {formatRelativeTime(med.last_taken_at)}</span>
                                            </div>
                                        )}

                                        {med.inventory_enabled && med.inventory_current !== undefined && (
                                            <div style={{ marginTop: '12px' }}>
                                                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                                                    <span>Остаток: {med.inventory_current} {med.unit || 'доз'}</span>
                                                    {med.inventory_total && (
                                                        <span>{Math.round((med.inventory_current / med.inventory_total) * 100)}%</span>
                                                    )}
                                                </div>
                                                <ProgressBar
                                                    percent={med.inventory_total ? (med.inventory_current / med.inventory_total) * 100 : 0}
                                                    style={{
                                                        '--track-width': '6px',
                                                        '--fill-color': med.inventory_current <= (med.inventory_warning_threshold || 0) ? 'var(--adm-color-danger)' : 'var(--adm-color-primary)'
                                                    }}
                                                />
                                            </div>
                                        )}
                                    </div>

                                    {med.is_active && (
                                        <div style={{ marginTop: '20px' }}>
                                            <Button
                                                block
                                                color="primary"
                                                fill="outline"
                                                onClick={() => handleLogIntake(med)}
                                                loading={intakeMutation.isPending && intakeMutation.variables?.id === med._id}
                                                disabled={(med.intakes_today || 0) >= med.schedule.times.length}
                                                style={{ borderRadius: '8px' }}
                                            >
                                                {(med.intakes_today || 0) >= med.schedule.times.length ? 'Принято на сегодня' : 'Отметить прием'}
                                            </Button>
                                        </div>
                                    )}
                                </div>
                            </Card>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
