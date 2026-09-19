import { useState, useMemo } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import { PullToRefresh } from 'antd-mobile';
import { Download } from 'lucide-react';
import { usePet } from '../hooks/usePet';
import { historyConfig } from '../utils/historyConfig';
import { HistoryItem } from '../components/HistoryItem';
import { HistoryChart } from '../components/HistoryChart';
import { ExportModal } from '../components/ExportModal';
import { usePetTilesSettings } from '../hooks/usePetTilesSettings';
import { tilesConfig } from '../utils/tilesConfig';
import { typeIconMap } from '../utils/constants';
import { healthRecordsService, type TimelineResponse } from '../services/healthRecords.service';
import { HistoryItemSkeleton } from '../components/Skeletons';
import { hapticFeedback } from '../utils/haptic';

/** Format a YYYY-MM-DD dateStr as a friendly Russian relative or absolute label. */
function formatDateHeader(dateStr: string): string {
    const parts = dateStr.split('-');
    if (parts.length !== 3) return dateStr;

    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(today.getDate() - 1);

    const pad = (n: number) => n.toString().padStart(2, '0');
    const todayStr = `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`;
    const yesterdayStr = `${yesterday.getFullYear()}-${pad(yesterday.getMonth() + 1)}-${pad(yesterday.getDate())}`;

    if (dateStr === todayStr) return 'Сегодня';
    if (dateStr === yesterdayStr) return 'Вчера';
    return `${parts[2]}.${parts[1]}.${parts[0]}`;
}

/** Sentinel value for the "all" filter chip. */
const FILTER_ALL = 'all';

export function History() {
    const { selectedPetId } = usePet();
    const { tilesSettings } = usePetTilesSettings(selectedPetId);
    const [filterType, setFilterType] = useState<string>(FILTER_ALL);
    const [exportVisible, setExportVisible] = useState(false);
    const [viewMode, setViewMode] = useState<'list' | 'chart'>('list');

    // Build filter chips from the tiles the user has enabled. "Все" first,
    // then each visible type. Chip = lucide icon + label.
    const filterChips = useMemo(() => {
        const visibleTiles = tilesConfig
            .filter(tile => tilesSettings.visible[tile.id] !== false)
            .sort((a, b) => {
                const aIndex = tilesSettings.order.indexOf(a.id);
                const bIndex = tilesSettings.order.indexOf(b.id);
                return (aIndex === -1 ? 999 : aIndex) - (bIndex === -1 ? 999 : bIndex);
            });
        return [
            { id: FILTER_ALL, label: 'Все', Icon: null },
            ...visibleTiles.map(tile => {
                const cfg = historyConfig[tile.id as keyof typeof historyConfig];
                return {
                    id: tile.id,
                    label: cfg?.displayName || tile.title,
                    Icon: typeIconMap[tile.id as keyof typeof typeIconMap] || null,
                };
            }),
        ];
    }, [tilesSettings]);

    // Timeline query — single fetch, single source for the whole feed.
    // The backend's timeline endpoint returns all record types mixed
    // (with `record_type` on each item); we filter client-side from the
    // chip selection so toggling chips is instant, no round-trip.
    const pageSize = 100;
    const {
        data,
        fetchNextPage,
        hasNextPage,
        isFetchingNextPage,
        isLoading,
        error,
        refetch,
    } = useInfiniteQuery({
        queryKey: ['history-timeline', selectedPetId],
        queryFn: async ({ pageParam = 1 }) => {
            return healthRecordsService.getTimeline(selectedPetId!, pageParam as number, pageSize, 'all');
        },
        getNextPageParam: (lastPage: TimelineResponse) => {
            return lastPage.page * pageSize < lastPage.total ? lastPage.page + 1 : undefined;
        },
        initialPageParam: 1,
        enabled: !!selectedPetId,
    });

    const allRecords = data?.pages.flatMap(page => page.items) || [];

    // Apply chip filter client-side.
    const filteredRecords = useMemo(() => {
        if (filterType === FILTER_ALL) return allRecords;
        return allRecords.filter(r => r.record_type === filterType);
    }, [allRecords, filterType]);

    // Group by date for the section headers.
    const groupedItems = useMemo(() => {
        const groups: Record<string, any[]> = {};
        for (const item of filteredRecords) {
            const dateStr = String(item.date_time ?? '').split(' ')[0];
            if (!groups[dateStr]) groups[dateStr] = [];
            groups[dateStr].push(item);
        }
        return Object.entries(groups).sort(([a], [b]) => b.localeCompare(a));
    }, [filteredRecords]);

    const handleFilterChange = (id: string) => {
        hapticFeedback('light');
        setFilterType(id);
    };

    const handleViewModeChange = (mode: 'list' | 'chart') => {
        hapticFeedback('light');
        setViewMode(mode);
    };

    if (!selectedPetId) {
        return (
            <div style={{ minHeight: '100vh', padding: 'var(--spacing-lg)' }}>
                <p>Выберите животное в меню навигации для просмотра истории</p>
            </div>
        );
    }

    const content = (() => {
        if (isLoading) {
            return (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <HistoryItemSkeleton />
                    <HistoryItemSkeleton />
                    <HistoryItemSkeleton />
                </div>
            );
        }

        if (error) {
            return (
                <p style={{ color: 'var(--app-danger-color)', textAlign: 'center', padding: '32px 0' }}>
                    Ошибка загрузки данных
                </p>
            );
        }

        if (groupedItems.length === 0) {
            return (
                <p style={{ color: 'var(--app-text-secondary)', textAlign: 'center', padding: '32px 0' }}>
                    Нет записей
                </p>
            );
        }

        return (
            <>
                {groupedItems.map(([dateStr, itemsForDate]) => (
                    <div key={dateStr} style={{ marginBottom: 'var(--spacing-lg)' }}>
                        <h3
                            className="section-header"
                            style={{ marginBottom: '10px', paddingLeft: 4 }}
                        >
                            {formatDateHeader(dateStr)}
                        </h3>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                            {itemsForDate.map((item: any, index: number) => {
                                const type = item.record_type;
                                const config = historyConfig[type as keyof typeof historyConfig];
                                if (!config) return null;
                                return (
                                    <div
                                        key={item._id}
                                        className={`animate-slide-up animate-stagger-${Math.min(index + 1, 6)}`}
                                    >
                                        <HistoryItem
                                            item={item}
                                            config={config}
                                            type={type}
                                            activeTab={type}
                                        />
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                ))}

                {hasNextPage && (
                    <div style={{
                        marginTop: '24px',
                        paddingTop: '24px',
                        borderTop: '1px solid var(--app-border-color)',
                        display: 'flex',
                        justifyContent: 'center',
                    }}>
                        <button
                            type="button"
                            onClick={() => {
                                hapticFeedback('light');
                                fetchNextPage();
                            }}
                            disabled={isFetchingNextPage}
                            style={{
                                padding: '10px 24px',
                                borderRadius: 'var(--app-border-radius)',
                                border: '1px solid var(--app-border-color)',
                                background: 'var(--app-card-background)',
                                color: 'var(--app-accent-deep)',
                                fontWeight: 600,
                                fontSize: 'var(--text-sm)',
                                cursor: isFetchingNextPage ? 'not-allowed' : 'pointer',
                                opacity: isFetchingNextPage ? 0.6 : 1,
                            }}
                        >
                            {isFetchingNextPage ? 'Загрузка...' : 'Загрузить ещё'}
                        </button>
                    </div>
                )}
            </>
        );
    })();

    return (
        <div className="page-container">
            <div className="max-width-container">
                <div className="safe-area-padding" style={{
                    marginBottom: 'var(--spacing-md)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    minHeight: '40px',
                }}>
                    <h1 className="display-headline" style={{ fontSize: '24px', margin: 0 }}>
                        История записей
                    </h1>
                    <button
                        type="button"
                        onClick={() => setExportVisible(true)}
                        style={{
                            background: 'transparent',
                            border: 'none',
                            color: 'var(--app-accent-deep)',
                            fontWeight: 500,
                            fontSize: 'var(--text-sm)',
                            cursor: 'pointer',
                            padding: '8px 4px',
                            display: 'flex',
                            alignItems: 'center',
                            gap: 6,
                        }}
                    >
                        <Download size={16} strokeWidth={2} style={{ display: 'block' }} />
                        Экспорт
                    </button>
                </div>

                {/* Type filter — horizontal scrollable chip rail.
                   Single-select: "Все" + each visible tile type. */}
                <div
                    className="history-filter-rail"
                    role="tablist"
                    aria-label="Фильтр по типу записи"
                >
                    {filterChips.map(chip => {
                        const active = chip.id === filterType;
                        const Icon = chip.Icon;
                        return (
                            <button
                                key={chip.id}
                                type="button"
                                role="tab"
                                aria-selected={active}
                                onClick={() => handleFilterChange(chip.id)}
                                className={`history-filter-chip ${active ? 'history-filter-chip--active' : ''}`}
                            >
                                {Icon ? <Icon size={14} strokeWidth={2.4} aria-hidden /> : null}
                                <span>{chip.label}</span>
                            </button>
                        );
                    })}
                </div>

                {/* View mode toggle — compact pill, sits flush right */}
                <div style={{
                    display: 'flex',
                    justifyContent: 'flex-end',
                    marginBottom: 'var(--spacing-md)',
                }}>
                    <div style={{
                        display: 'flex',
                        backgroundColor: 'var(--app-card-background)',
                        padding: 3,
                        borderRadius: '999px',
                        boxShadow: 'var(--app-shadow-light)',
                        border: '1px solid var(--app-border-color)',
                    }}>
                        <button
                            type="button"
                            onClick={() => handleViewModeChange('list')}
                            style={{
                                background: viewMode === 'list' ? 'var(--app-primary-color)' : 'transparent',
                                color: viewMode === 'list' ? '#FFFFFF' : 'var(--app-text-secondary)',
                                border: 'none',
                                borderRadius: '999px',
                                padding: '4px 14px',
                                fontSize: 'var(--text-xs)',
                                fontWeight: 600,
                                cursor: 'pointer',
                                transition: 'all 180ms ease',
                            }}
                        >
                            Список
                        </button>
                        <button
                            type="button"
                            onClick={() => handleViewModeChange('chart')}
                            style={{
                                background: viewMode === 'chart' ? 'var(--app-primary-color)' : 'transparent',
                                color: viewMode === 'chart' ? '#FFFFFF' : 'var(--app-text-secondary)',
                                border: 'none',
                                borderRadius: '999px',
                                padding: '4px 14px',
                                fontSize: 'var(--text-xs)',
                                fontWeight: 600,
                                cursor: 'pointer',
                                transition: 'all 180ms ease',
                            }}
                        >
                            График
                        </button>
                    </div>
                </div>

                <div style={{ minHeight: '400px' }}>
                    {viewMode === 'list' ? (
                        <PullToRefresh
                            onRefresh={async () => {
                                hapticFeedback('medium');
                                await refetch();
                            }}
                            headHeight={48}
                        >
                            <div style={{
                                display: 'flex',
                                flexDirection: 'column',
                                gap: '4px',
                                paddingLeft: 'max(16px, env(safe-area-inset-left))',
                                paddingRight: 'max(16px, env(safe-area-inset-right))',
                                paddingTop: '8px',
                            }}>
                                {content}
                            </div>
                        </PullToRefresh>
                    ) : (
                        <div className="safe-area-padding">
                            {/* Chart view uses the selected type; "Все" falls
                                back to feeding (the most charted metric). */}
                            <HistoryChart
                                type={filterType === FILTER_ALL ? 'feeding' : filterType}
                                petId={selectedPetId}
                            />
                        </div>
                    )}
                </div>
            </div>

            <ExportModal
                visible={exportVisible}
                onClose={() => setExportVisible(false)}
                petId={selectedPetId}
                defaultType={filterType === FILTER_ALL ? 'feeding' : filterType}
            />
        </div>
    );
}
