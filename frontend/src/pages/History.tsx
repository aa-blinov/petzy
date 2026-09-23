import { useState, useMemo } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import { PullToRefresh } from 'antd-mobile';
import { Download, Notebook, ChevronDown, Rows3 } from 'lucide-react';
import { usePet } from '../hooks/usePet';
import { useEventTypes } from '../hooks/useEventTypes';
import { buildEventDisplayConfigs } from '../utils/eventDisplay';
import { HistoryItem } from '../components/HistoryItem';
import { HistoryChart } from '../components/HistoryChart';
import { EmptyState } from '../components/EmptyState';
import { ExportModal, ALL_TYPES } from '../components/ExportModal';
import { HistoryFilterSheet, type HistoryFilterOption } from '../components/HistoryFilterSheet';
import { usePetTilesSettings } from '../hooks/usePetTilesSettings';
import { buildTiles } from '../utils/tilesConfig';
import { healthRecordsService, type TimelineResponse, type HealthRecord } from '../services/healthRecords.service';
import { SkeletonList } from '../components/Skeletons';
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
    const { eventTypes } = useEventTypes();
    const historyConfig = useMemo(() => buildEventDisplayConfigs(eventTypes), [eventTypes]);
    const [filterType, setFilterType] = useState<string>(FILTER_ALL);
    const [exportVisible, setExportVisible] = useState(false);
    const [filterSheetVisible, setFilterSheetVisible] = useState(false);

    // Build filter options from every registered type. "Все" first, then
    // each type — shown as a grid of tiles in HistoryFilterSheet, same
    // look as the dashboard's "+" sheet.
    //
    // `tilesSettings.visible` only decides what the dashboard's quick-add
    // sheet offers — hiding a rarely-logged type there so it doesn't
    // clutter "+" says nothing about whether the user still wants to
    // filter their History by it (they usually do: a type hidden from
    // quick-add still has past records worth looking back at). This used
    // to filter by that same visibility, so a type hidden from the
    // dashboard silently vanished from the History filter too, with no
    // way to reach it short of un-hiding it again in Settings. Only the
    // *order* is still worth sharing — it's the arrangement the user
    // already knows from the dashboard.
    const filterOptions: HistoryFilterOption[] = useMemo(() => {
        const orderedTiles = buildTiles(eventTypes)
            .sort((a, b) => {
                const aIndex = tilesSettings.order.indexOf(a.id);
                const bIndex = tilesSettings.order.indexOf(b.id);
                return (aIndex === -1 ? 999 : aIndex) - (bIndex === -1 ? 999 : bIndex);
            });
        return [
            { id: FILTER_ALL, label: 'Все', color: 'gray', Icon: Rows3 },
            ...orderedTiles.map(tile => {
                const cfg = historyConfig[tile.id];
                return {
                    id: tile.id,
                    label: cfg?.displayName || tile.title,
                    color: tile.color,
                    Icon: cfg?.icon || null,
                };
            }),
        ];
    }, [tilesSettings, eventTypes, historyConfig]);

    const activeFilterOption = filterOptions.find(o => o.id === filterType) ?? filterOptions[0];

    // Timeline query — the chip's filter is sent straight to the backend
    // (which already supports a `type` param) rather than always fetching
    // `type=all` and filtering the loaded page client-side. The client
    // filter looked instant, but it only ever saw whatever mixed page
    // had already loaded — a type that logs rarely next to one that logs
    // constantly (e.g. weight next to feeding) could read as empty, or
    // silently drop older matches, until "Загрузить ещё" was tapped
    // enough times to page past the noise. filterType is part of the
    // query key, so switching chips starts its own fresh, correctly
    // paginated fetch instead of re-slicing an unrelated one.
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
        queryKey: ['history-timeline', selectedPetId, filterType],
        queryFn: async ({ pageParam = 1 }) => {
            return healthRecordsService.getTimeline(selectedPetId!, pageParam as number, pageSize, filterType);
        },
        getNextPageParam: (lastPage: TimelineResponse) => {
            return lastPage.page * pageSize < lastPage.total ? lastPage.page + 1 : undefined;
        },
        initialPageParam: 1,
        enabled: !!selectedPetId,
    });

    // Already filtered server-side by `filterType` — kept as its own name
    // (rather than inlining `data?.pages...` everywhere below) since
    // that's still what every consumer below conceptually wants: "the
    // records for the current filter."
    const filteredRecords = useMemo(() => data?.pages.flatMap(page => page.items) || [], [data]);

    // Group by date for the section headers.
    const groupedItems = useMemo(() => {
        const groups: Record<string, HealthRecord[]> = {};
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

    if (!selectedPetId) {
        return (
            <div style={{ minHeight: '100vh', padding: 'var(--spacing-lg)' }}>
                <p>Выберите животное в меню навигации для просмотра истории</p>
            </div>
        );
    }

    const content = (() => {
        if (isLoading) {
            return <SkeletonList count={4} gap={12} />;
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
                <EmptyState
                    icon={Notebook}
                    title="Записей пока нет"
                    description="Кормления, вес, лекарства и прививки появятся здесь, как только вы их добавите"
                />
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
                            {itemsForDate.map((item: HealthRecord) => {
                                const type = item.record_type;
                                if (!type) return null;
                                const config = historyConfig[type];
                                if (!config) return null;
                                return (
                                    <HistoryItem
                                        key={item._id}
                                        item={item}
                                        config={config}
                                        type={type}
                                        activeTab={type}
                                    />
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
                {/* Header — one row, not three.
                   This screen used to stack a title row, the filter rail
                   and a third row holding just the list/chart pill, so
                   three bands of chrome pushed the records below the
                   fold. Export is icon-only (it is an occasional action,
                   and the tab is already labelled "История", so "История
                   записей" was saying it twice). The old list/chart
                   toggle is gone too — trends are no longer a mode you
                   switch into instead of the list, they're their own
                   section shown above it (see below). */}
                <div className="safe-area-padding" style={{
                    marginBottom: 'var(--spacing-md)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: 'var(--spacing-sm)',
                    minHeight: '40px',
                }}>
                    <h1 className="display-headline" style={{ fontSize: '24px', margin: 0 }}>
                        История
                    </h1>
                    <button
                        type="button"
                        onClick={() => setExportVisible(true)}
                        aria-label="Экспорт"
                        title="Экспорт"
                        style={{
                            background: 'transparent',
                            border: 'none',
                            color: 'var(--app-accent-deep)',
                            cursor: 'pointer',
                            padding: 10,
                            display: 'flex',
                            alignItems: 'center',
                        }}
                    >
                        <Download size={20} strokeWidth={2} style={{ display: 'block' }} />
                    </button>
                </div>

                {/* Type filter — a single trigger opening a bottom sheet
                   (HistoryFilterSheet), same grid-of-tiles pattern as the
                   dashboard's "+" sheet, instead of a horizontally
                   scrolling chip rail that gave no hint it scrolled. */}
                <button
                    type="button"
                    onClick={() => {
                        hapticFeedback('light');
                        setFilterSheetVisible(true);
                    }}
                    aria-haspopup="dialog"
                    className="history-filter-trigger"
                >
                    {activeFilterOption.Icon && (
                        <activeFilterOption.Icon size={16} strokeWidth={2.4} aria-hidden />
                    )}
                    <span>{activeFilterOption.label}</span>
                    <ChevronDown size={16} strokeWidth={2.4} aria-hidden style={{ marginLeft: 2 }} />
                </button>

                <HistoryFilterSheet
                    visible={filterSheetVisible}
                    onClose={() => setFilterSheetVisible(false)}
                    options={filterOptions}
                    activeId={filterType}
                    onSelect={handleFilterChange}
                />

                {/* Trends — a chart across every event type mixed together
                   doesn't mean anything, so this section only appears once
                   a specific type is filtered, sitting above the (also
                   filtered) event list below it rather than replacing it.
                   Also skipped when that type has no records at all yet —
                   otherwise a type with zero history showed its own "Нет
                   данных за период" right above the list's identical
                   "Записей пока нет", two empty states saying the same
                   thing back to back. */}
                {filterType !== FILTER_ALL && filteredRecords.length > 0 && (
                    <div className="safe-area-padding" style={{ marginTop: 'var(--spacing-md)' }}>
                        <h3 className="section-header" style={{ marginBottom: 0, paddingLeft: 4 }}>
                            Тренды
                        </h3>
                        <HistoryChart type={filterType} petId={selectedPetId} />
                    </div>
                )}

                <div style={{ minHeight: '400px' }}>
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
                </div>
            </div>

            <ExportModal
                visible={exportVisible}
                onClose={() => setExportVisible(false)}
                petId={selectedPetId}
                // "Все" now maps to the real all-types export instead of
                // silently pre-selecting feeding.
                defaultType={filterType === FILTER_ALL ? ALL_TYPES : filterType}
            />
        </div>
    );
}
