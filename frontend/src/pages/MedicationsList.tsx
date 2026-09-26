import { useState } from 'react';
import { formatDate, formatTime } from '../utils/dateUtils';
import { showToast } from '../utils/toast';
import { getApiErrorMessage } from '../utils/apiError';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, Card, Tag, Dialog, Input, PullToRefresh } from 'antd-mobile';
import { AddOutline, ClockCircleOutline } from 'antd-mobile-icons';
import { useNavigate } from 'react-router-dom';
import { Pill, Droplets, Syringe, Pencil, Trash2 } from 'lucide-react';
import { medicationsListQuery, medicationsService, type Medication } from '../services/medications.service';
import { usePet } from '../hooks/usePet';
import { useAuth } from '../hooks/useAuth';
import { MedicationCardSkeleton, SkeletonList } from '../components/Skeletons';
import { EmptyState } from '../components/EmptyState';
import { UserAvatar } from '../components/UserAvatar';
import { hapticFeedback } from '../utils/haptic';
import { RAN_OUT_MESSAGE, formatAmount, isAmountDraft, parseAmount, stockSummary } from '../utils/stock';
import { CardChevron } from '../components/CardChevron';
import { SwipeableRow } from '../components/SwipeableRow';

export function MedicationsList() {
    const { selectedPetId } = usePet();
    const { username: currentUsername } = useAuth();
    const navigate = useNavigate();
    const queryClient = useQueryClient();

    const { data: medications = [], isLoading, refetch } = useQuery({
        ...medicationsListQuery(selectedPetId ?? ''),
        enabled: !!selectedPetId,
    });

    const [logIntakeDialog, setLogIntakeDialog] = useState<{
        visible: boolean;
        medication: Medication | null;
        // Typed text, not a number: «0,» mid-typing must survive.
        dose: string;
    }>({
        visible: false,
        medication: null,
        dose: '1'
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
            // Both from the local wall clock, not toISOString(): that
            // emits the UTC date, which disagrees with the local date for
            // several hours around midnight (5 at UTC+5) — the intake
            // landed under yesterday's date paired with today's time,
            // so it fell outside every "today" query (intakes_today,
            // the upcoming-dose widget) until the offset window passed.
            const now = new Date();
            return medicationsService.logIntake(id, {
                date: formatDate(now),
                time: formatTime(now),
                dose_taken: dose,
            });
        },
        onSuccess: ({ ran_out }) => {
            queryClient.invalidateQueries({ queryKey: ['medications'] });
            queryClient.invalidateQueries({ queryKey: ['pets'] });
            // The dose is recorded either way; an empty stock is news.
            if (ran_out) showToast.info(RAN_OUT_MESSAGE, { duration: 3500 });
            else showToast.success('Приём отмечен');
        },
        onError: (err: unknown) => {
            showToast.failure(getApiErrorMessage(err, 'Не удалось сохранить'));
        }
    });

    const deleteMutation = useMutation({
        mutationFn: (id: string) => medicationsService.delete(id),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['medications'] });
            showToast.success('Курс удалён');
        }
    });

    const handleDelete = (med: Medication) => {
        hapticFeedback('light');
        setDeleteDialog({ visible: true, medication: med });
    };

    const handleLogIntake = (med: Medication) => {
        hapticFeedback('light');
        setLogIntakeDialog({
            visible: true,
            medication: med,
            dose: formatAmount(med.default_dose || 1)
        });
    };

    const confirmLogIntake = () => {
        if (!logIntakeDialog.medication) return;
        const dose = parseAmount(logIntakeDialog.dose);
        if (!dose || dose <= 0) {
            showToast.failure('Укажите, сколько дали');
            return;
        }
        intakeMutation.mutate({ id: logIntakeDialog.medication._id, dose });
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
        <div className="page-container">
            <div className="max-width-container">
                <div className="safe-area-padding" style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: 'var(--spacing-lg)',
                    minHeight: '40px',
                }}>
                    <h1 className="display-headline" style={{ fontSize: '28px', margin: 0 }}>
                        Препараты
                    </h1>
                    {medications.length > 0 && (
                        <button
                            type="button"
                            onClick={() => navigate('/medications/new')}
                            style={{
                                background: 'transparent',
                                border: 'none',
                                color: 'var(--app-accent-deep)',
                                fontWeight: 600,
                                fontSize: 'var(--text-sm)',
                                cursor: 'pointer',
                                padding: '8px 12px',
                                display: 'flex',
                                alignItems: 'center',
                                gap: 4,
                            }}
                        >
                            <AddOutline style={{ fontSize: 20 }} />
                            Добавить
                        </button>
                    )}
                </div>

                {isLoading ? (
                    <SkeletonList
                        count={3}
                        gap={undefined /* use default token gap */}
                        render={() => <MedicationCardSkeleton />}
                    />
                ) : medications.length === 0 ? (
                    <EmptyState
                        icon={Pill}
                        title="Здесь будут курсы препаратов"
                        description="Добавьте лекарство, и Petzy напомнит о приёме и покажет остаток"
                        actionLabel="Добавить препарат"
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
                        {medications.map((med) => (
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
                                                {!med.is_active && <Tag color="default">Архив</Tag>}
                                            </div>
                                            <p style={{ margin: 0, fontSize: 'var(--text-sm)', color: 'var(--app-text-secondary)' }}>
                                                {med.strength ? `${med.strength}` : med.type}
                                                <span style={{ margin: `0 var(--spacing-xs)`, color: 'var(--app-divider-color)' }}>|</span>
                                                По {formatAmount(med.default_dose || 1)} {med.dose_unit || 'ед.'}
                                            </p>
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
                                            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-xs)', marginBottom: 'var(--spacing-sm)', color: 'var(--app-primary-text)' }}>
                                                <span>Последний приём: {formatRelativeTime(med.last_taken_at)}</span>
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
                                                    gap: '6px',
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
                                                            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--app-text-secondary)', marginTop: 2 }}>
                                                                {stock.lasts}
                                                            </div>
                                                        )}
                                                    </div>
                                                    <Button
                                                        size="small"
                                                        fill="outline"
                                                        onClick={() => openRestock(med)}
                                                        style={{ flexShrink: 0, borderRadius: 'var(--radius-sm)' }}
                                                    >
                                                        Пополнить
                                                    </Button>
                                                </div>
                                            );
                                        })()}
                                    </div>

                                    </div>
                                    {/* Centred on the details, not the whole card: beside the
                                        «Отметить приём» button it would read as the button's. */}
                                    <CardChevron />
                                    </div>
                                    {med.is_active && (
                                        // Logging a dose is its own action, not a tap on the card
                                        // (a disabled button's click must not open the form either).
                                        <div style={{ marginTop: 'var(--spacing-xl)' }} onClick={(e) => e.stopPropagation()}>
                                            <Button
                                                block
                                                color="primary"
                                                fill="outline"
                                                onClick={() => handleLogIntake(med)}
                                                loading={intakeMutation.isPending && intakeMutation.variables?.id === med._id}
                                                disabled={(med.intakes_today || 0) >= med.schedule.times.length}
                                                style={{ borderRadius: 'var(--radius-sm)' }}
                                            >
                                                {(med.intakes_today || 0) >= med.schedule.times.length ? 'На сегодня всё' : `Отметить приём (${formatAmount(med.default_dose || 1)} ${med.dose_unit || ''})`}
                                            </Button>
                                        </div>
                                    )}
                                </div>
                            </Card>
                            </SwipeableRow>
                        ))}
                    </div>
                    </PullToRefresh>
                )}
            </div>

            <Dialog
                visible={logIntakeDialog.visible}
                title="Подтвердите приём"
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
                                    value={logIntakeDialog.dose}
                                    type="text"
                                    inputMode="decimal"
                                    onChange={val => {
                                        if (isAmountDraft(val)) setLogIntakeDialog(prev => ({ ...prev, dose: val }));
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
                afterClose={() => setLogIntakeDialog({ visible: false, medication: null, dose: '1' })}
                actions={[
                    {
                        key: 'confirm',
                        text: 'Записать',
                        bold: true,
                        onClick: confirmLogIntake
                    },
                    {
                        key: 'cancel',
                        text: 'Отмена',
                        onClick: () => setLogIntakeDialog(prev => ({ ...prev, visible: false }))
                    },
                ]}
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
                title="Удаление курса"
                content={
                    deleteDialog.medication && (
                        <span>Удалить курс «{deleteDialog.medication.name}» и всю его историю?</span>
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
