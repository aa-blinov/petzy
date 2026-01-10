import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, Card, ProgressBar, Toast, Tag, Dialog, Input } from 'antd-mobile';
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
        queryFn: () => {
            const clientDate = new Date().toISOString().split('T')[0];
            return medicationsService.getList(selectedPetId!, clientDate);
        },
        enabled: !!selectedPetId,
    });

    const [logIntakeDialog, setLogIntakeDialog] = useState<{
        visible: boolean;
        medication: Medication | null;
        dose: number;
    }>({
        visible: false,
        medication: null,
        dose: 1
    });

    const [deleteDialog, setDeleteDialog] = useState<{
        visible: boolean;
        medication: Medication | null;
    }>({
        visible: false,
        medication: null
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
        setDeleteDialog({
            visible: true,
            medication: med
        });
    };

    const handleLogIntake = (med: Medication) => {
        setLogIntakeDialog({
            visible: true,
            medication: med,
            dose: med.default_dose || 1
        });
    };

    const confirmLogIntake = () => {
        if (!logIntakeDialog.medication) return;
        intakeMutation.mutate({
            id: logIntakeDialog.medication._id,
            dose: logIntakeDialog.dose
        });
        setLogIntakeDialog(prev => ({ ...prev, visible: false }));
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

    const getFormFactorIcon = (formFactor?: string) => {
        switch (formFactor) {
            case 'tablet': return '💊';
            case 'liquid': return '💧';
            case 'injection': return '💉';
            default: return '💊';
        }
    };

    if (isLoading) return <LoadingSpinner />;

    return (
        <div className="page-container">
            <div className="max-width-container">
                <div className="safe-area-padding" style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: 'var(--spacing-lg)',
                    minHeight: '40px',
                }}>
                    <h2 style={{ margin: 0, fontSize: 'var(--text-xxl)', fontWeight: 600 }}>Прием препаратов</h2>
                    <Button
                        color="primary"
                        fill="solid"
                        size="small"
                        onClick={() => navigate('/medications/new')}
                        style={{
                            borderRadius: 'var(--radius-md)',
                            fontWeight: 500,
                            display: 'flex',
                            alignItems: 'center',
                            gap: 'var(--spacing-xs)'
                        }}
                    >
                        <AddOutline style={{ fontSize: '18px' }} /> Добавить
                    </Button>
                </div>

                {medications.length === 0 ? (
                    <div className="safe-area-padding" style={{
                        textAlign: 'center',
                        color: 'var(--adm-color-weak)',
                        paddingTop: 'var(--spacing-xl)',
                        paddingBottom: 'var(--spacing-xl)',
                    }}>
                        Нет назначенных лекарств
                    </div>
                ) : (
                    <div className="safe-area-padding" style={{
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 'var(--spacing-md)',
                        marginTop: 'var(--spacing-sm)',
                    }}>
                        {medications.map(med => (
                            <Card key={med._id} style={{
                                borderRadius: 'var(--radius-md)',
                                border: 'none',
                                boxShadow: 'var(--app-shadow)'
                            }}>
                                <div style={{ padding: 'var(--spacing-lg)' }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                        <div>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-sm)', marginBottom: 'var(--spacing-xs)', flexWrap: 'wrap' }}>
                                                <span style={{ fontSize: 'var(--text-xl)' }}>{getFormFactorIcon(med.form_factor)}</span>
                                                <h3 style={{ margin: 0, fontSize: 'var(--text-lg)', fontWeight: 600 }}>{med.name}</h3>
                                                {!med.is_active && <Tag color="default">Архив</Tag>}
                                            </div>
                                            <p style={{ margin: 0, fontSize: 'var(--text-sm)', color: 'var(--app-text-secondary)' }}>
                                                {med.strength ? `${med.strength}` : med.type}
                                                <span style={{ margin: `0 var(--spacing-xs)`, color: 'var(--app-divider-color)' }}>|</span>
                                                По {med.default_dose || 1} {med.dose_unit || 'ед.'}
                                            </p>
                                        </div>
                                        <div style={{ display: 'flex', gap: 'var(--spacing-sm)' }}>
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

                                    <div style={{ marginTop: 'var(--spacing-md)', fontSize: 'var(--text-xs)', color: 'var(--app-text-secondary)', lineHeight: 'var(--line-height-normal)' }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-xs)', marginBottom: 'var(--spacing-sm)' }}>
                                            <ClockCircleOutline />
                                            <span>
                                                {med.schedule.days.length === 7 ? 'Ежедневно' : 'В выбранные дни'} в {med.schedule.times.join(', ')}
                                            </span>
                                        </div>

                                        {med.last_taken_at && (
                                            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-xs)', marginBottom: 'var(--spacing-sm)', color: 'var(--app-primary-color)' }}>
                                                <span>Последний прием: {formatRelativeTime(med.last_taken_at)}</span>
                                            </div>
                                        )}

                                        {med.inventory_enabled && med.inventory_current !== undefined && (
                                            <div style={{ marginTop: 'var(--spacing-md)' }}>
                                                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--spacing-xs)' }}>
                                                    <span>Остаток: {med.inventory_current} {med.dose_unit || 'доз'}</span>
                                                    {med.inventory_total && (
                                                        <span>{Math.round((med.inventory_current / med.inventory_total) * 100)}%</span>
                                                    )}
                                                </div>
                                                <ProgressBar
                                                    percent={med.inventory_total ? (med.inventory_current / med.inventory_total) * 100 : 0}
                                                    style={{
                                                        '--track-width': '6px',
                                                        '--fill-color': med.inventory_current <= (med.inventory_warning_threshold || 0) ? 'var(--app-danger-color)' : 'var(--app-primary-color)'
                                                    }}
                                                />
                                            </div>
                                        )}
                                    </div>

                                    {med.is_active && (
                                        <div style={{ marginTop: 'var(--spacing-xl)' }}>
                                            <Button
                                                block
                                                color="primary"
                                                fill="outline"
                                                onClick={() => handleLogIntake(med)}
                                                loading={intakeMutation.isPending && intakeMutation.variables?.id === med._id}
                                                disabled={(med.intakes_today || 0) >= med.schedule.times.length}
                                                style={{ borderRadius: 'var(--radius-sm)' }}
                                            >
                                                {(med.intakes_today || 0) >= med.schedule.times.length ? 'На сегодня всё' : `Отметить прием (${med.default_dose || 1} ${med.dose_unit || ''})`}
                                            </Button>
                                        </div>
                                    )}
                                </div>
                            </Card>
                        ))}
                    </div>
                )}
            </div>

            <Dialog
                visible={logIntakeDialog.visible}
                title="Подтвердите прием"
                content={
                    logIntakeDialog.medication && (
                        <div style={{ textAlign: 'center' }}>
                            <div style={{ marginBottom: 'var(--spacing-lg)', fontSize: 'var(--text-sm)' }}>
                                {logIntakeDialog.medication.name} {logIntakeDialog.medication.strength}
                            </div>
                            <div style={{ fontSize: 'var(--text-lg)', fontWeight: 600, marginBottom: 'var(--spacing-lg)' }}>
                                Сколько дали?
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px' }}>
                                <Input
                                    value={logIntakeDialog.dose.toString()}
                                    type="text"
                                    inputMode="decimal"
                                    onChange={val => {
                                        if (val === '' || /^\d*\.?\d*$/.test(val)) {
                                            setLogIntakeDialog(prev => ({ ...prev, dose: val === '' ? 0 : parseFloat(val) }));
                                        }
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
                                    {logIntakeDialog.medication.dose_unit || 'ед.'}
                                </span>
                            </div>
                        </div>
                    )
                }
                onClose={() => setLogIntakeDialog(prev => ({ ...prev, visible: false }))}
                afterClose={() => setLogIntakeDialog({ visible: false, medication: null, dose: 1 })}
                actions={[
                    {
                        key: 'cancel',
                        text: 'Отмена',
                        onClick: () => setLogIntakeDialog(prev => ({ ...prev, visible: false }))
                    },
                    {
                        key: 'confirm',
                        text: 'Записать',
                        bold: true,
                        onClick: confirmLogIntake
                    },
                ]}
            />

            <Dialog
                visible={deleteDialog.visible}
                title="Удаление курса"
                content={
                    deleteDialog.medication && (
                        <span>Удалить курс "{deleteDialog.medication.name}" и всю его историю?</span>
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
                                deleteMutation.mutate(deleteDialog.medication._id);
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
