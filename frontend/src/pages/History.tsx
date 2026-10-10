import { useState, useMemo, lazy, Suspense } from 'react';
import { uniqueById } from '../utils/uniqueById';
import { useSearchParams } from 'react-router-dom';
import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { Button, PullToRefresh } from 'antd-mobile';
import { Download, Notebook, ChevronDown, Rows3 } from 'lucide-react';
import { usePet } from '../hooks/usePet';
import { useEventTypes } from '../hooks/useEventTypes';
import { buildEventDisplayConfigs } from '../utils/eventDisplay';
import { HistoryItem, SwipeHint } from '../components/HistoryItem';
import { useHiddenRecords } from '../utils/deferredDelete';
import { LoadingSpinner } from '../components/LoadingSpinner';

// recharts is most of this page's 365 KB chunk, and the chart only shows
// once a type filter is picked; fetch it then, not on every visit.
const HistoryChart = lazy(() => import('../components/HistoryChart').then((m) => ({ default: m.HistoryChart })));
import { EmptyState } from '../components/EmptyState';
import { NoPetState } from '../components/NoPetState';
import { LoadError } from '../components/LoadError';
import { ExportModal, ALL_TYPES } from '../components/ExportModal';
import { HistoryFilterSheet, type HistoryFilterOption } from '../components/HistoryFilterSheet';
import { usePetTilesSettings } from '../hooks/usePetTilesSettings';
import { eventTypesService } from '../services/eventTypes.service';
import { isTileShown } from '../utils/tilesConfig';
import { buildTiles } from '../utils/tilesConfig';
import { healthRecordsService, type TimelineResponse, type HealthRecord } from '../services/healthRecords.service';
import { SkeletonList } from '../components/Skeletons';
import { Fab } from '../components/Fab';
import { QuickAddSheet } from '../components/QuickAddSheet';
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
    const { selectedPetId, isLoading: petsLoading } = usePet();
    const { tilesSettings } = usePetTilesSettings(selectedPetId);
    const { eventTypes } = useEventTypes();
    const historyConfig = useMemo(() => buildEventDisplayConfigs(eventTypes), [eventTypes]);
    // «История веса» from a visit's form arrives with ?type=weight.
    //
    // The chosen type lives in the address, not only in state: a reload, a
    // «Назад» from a record's form and a shared link all land on the same
    // filtered screen. Before, the parameter was read once at mount and never
    // written, so the screen and the address disagreed the moment the filter
    // changed, and reloading dropped the filter.
    const [searchParams, setSearchParams] = useSearchParams();
    const filterType = searchParams.get('type') || FILTER_ALL;
    const [exportVisible, setExportVisible] = useState(false);
    const [filterSheetVisible, setFilterSheetVisible] = useState(false);
    // «Записать» from the history screen itself: the round «+» every list has (components/Fab), and the same
    // quick-add sheet the feed opens, so a record can be added from here too.
    const [addVisible, setAddVisible] = useState(false);

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
    // What this pet has records of (the catalogue is long: a pet that never had a fever is not offered «Температура» here), plus
    // what its «+» offers and the filter that is on.
    const usedTypes = useQuery({
        queryKey: ['used-types', selectedPetId],
        queryFn: () => eventTypesService.usedBy(selectedPetId!),
        enabled: !!selectedPetId,
        staleTime: 0,
    });
    const filterOptions: HistoryFilterOption[] = useMemo(() => {
        const used = new Set(usedTypes.data ?? []);
        const orderedTiles = buildTiles(eventTypes)
            .filter(tile => used.has(tile.id) || isTileShown(tilesSettings, tile.id) || tile.id === filterType)
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
    }, [tilesSettings, eventTypes, historyConfig, usedTypes.data, filterType]);

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
        // What another person wrote while the app was in the background is there when it comes back to the front.
        // The feed already refetches on focus (Dashboard); the shared default is off (App.tsx), so without this
        // the same app left History open showed yesterday's list until it was pulled down by hand.
        refetchOnWindowFocus: true,
    });

    // Already filtered server-side by `filterType` — kept as its own name
    // (rather than inlining `data?.pages...` everywhere below) since
    // that's still what every consumer below conceptually wants: "the
    // records for the current filter."
    // Records deleted a moment ago, «Отменить» still on offer, are left out.
    const hiddenRecords = useHiddenRecords();
    const filteredRecords = useMemo(
        () => uniqueById(data?.pages.flatMap(page => page.items) || []).filter(item => !hiddenRecords.has(item._id)),
        [data, hiddenRecords],
    );

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
        setSearchParams(
            prev => {
                const next = new URLSearchParams(prev);
                // «Все» is the absence of a filter, so the address stays clean.
                if (id === FILTER_ALL) next.delete('type');
                else next.set('type', id);
                return next;
            },
            // A filter is not a step back: «Назад» from it should leave the screen, not undo it.
            { replace: true },
        );
    };

    // The list of pets decides whether there is anything to show. While it loads there is no chosen pet yet
    // and no answer either, and «сначала добавьте питомца» said that to people whose pets were on the way.
    if (petsLoading) {
        return <LoadingSpinner fullscreen={false} />;
    }

    if (!selectedPetId) {
        return <NoPetState what="История" />;
    }

    const content = (() => {
        if (isLoading) {
            return <SkeletonList count={4} gap={12} />;
        }

        if (error) {
            return <LoadError what="историю" onRetry={refetch} />;
        }

        if (groupedItems.length === 0) {
            return (
                <EmptyState
                    icon={Notebook}
                    title={filterType === FILTER_ALL ? 'Записей пока нет' : `${activeFilterOption.label}: записей пока нет`}
                    description={filterType === FILTER_ALL ? 'Кормления, вес, лекарства и прививки появятся здесь, как только вы их добавите' : 'Они появятся здесь, как только вы их добавите. Другие записи видны, если выбрать «Все»'}
                    actionLabel="Записать событие"
                    onAction={() => setAddVisible(true)}
                />
            );
        }

        return (
            <>
                {/* The same rows, the same swipes and the same one-time hint as the feed: this
                    screen is the other half of the same list, not a different kind of one. */}
                <SwipeHint />
                {groupedItems.map(([dateStr, itemsForDate]) => (
                    <div key={dateStr} style={{ marginBottom: 'var(--spacing-lg)' }}>
                        <h2
                            className="section-header"
                            style={{ marginBottom: 'var(--spacing-sm)', paddingLeft: 4 }}
                        >
                            {formatDateHeader(dateStr)}
                        </h2>
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
                        <Button
                            fill="outline"
                            color="primary"
                            onClick={() => {
                                hapticFeedback('light');
                                fetchNextPage();
                            }}
                            disabled={isFetchingNextPage}
                            loading={isFetchingNextPage}
                        >
                            {isFetchingNextPage ? 'Загрузка...' : 'Загрузить ещё'}
                        </Button>
                    </div>
                )}
            </>
        );
    })();

    return (
        <div className="page-container fab-page">
            <div className="max-width-container">
                {/* Header — one row, not three.
                   This screen used to stack a title row, the filter rail
                   and a third row holding just the list/chart pill, so
                   three bands of chrome pushed the records below the
                   fold. Export sits in the title row with its label beside the icon
                   (an icon alone left the meaning to be guessed at). The old
                   list/chart toggle is gone too — trends are no longer a mode you
                   switch into instead of the list, they're their own
                   section shown above it (see below). */}
                <div className="safe-area-padding" style={{
                    marginBottom: 0,
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: 'var(--spacing-sm)',
                    minHeight: '40px',
                }}>
                    <h1 className="display-headline" style={{ fontSize: 'var(--text-xxl)', margin: 0 }}>
                        История
                    </h1>
                    <button
                        type="button"
                        onClick={() => setExportVisible(true)}
                        className="touch-target"
                        style={{
                            background: 'transparent',
                            border: '1px solid var(--app-primary-text)',
                            borderRadius: 'var(--radius-md)',
                            color: 'var(--app-accent-deep)',
                            cursor: 'pointer',
                            padding: '10px 12px',
                            display: 'flex',
                            alignItems: 'center',
                            gap: 'var(--spacing-xs)',
                            font: 'inherit',
                            fontSize: 'var(--text-sm)',
                            fontWeight: 500,
                        }}
                    >
                        <Download size={20} strokeWidth={2} style={{ display: 'block' }} />
                        {/* The word beside the icon: an icon alone left the meaning to be guessed at,
                            and this is the only way off this screen with the records. */}
                        Экспорт
                    </button>
                </div>
                {/* Лента is today and what's next; this is everything. Without
                    a word it read as the same list twice. Under the title row,
                    full width, so it doesn't wrap beside the export icon. */}
                <p className="safe-area-padding" style={{ margin: '0 0 var(--spacing-md)', fontSize: 'var(--text-sm)', color: 'var(--app-text-secondary)' }}>
                    Все записи за всё время и графики
                </p>

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
                    <ChevronDown size={16} strokeWidth={2.4} aria-hidden style={{ marginLeft: 'var(--spacing-xs)' }} />
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
                        <h2 className="section-header" style={{ marginBottom: 0, paddingLeft: 4 }}>
                            Тренды
                        </h2>
                        <Suspense fallback={<LoadingSpinner fullscreen={false} />}>
                            <HistoryChart type={filterType} petId={selectedPetId} />
                        </Suspense>
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

            {/* The round «+» the feed has, so a record can be written from the history itself instead of only
                from the feed. Same sheet, same quick-add grid. */}
            <Fab label="Добавить запись" onClick={() => setAddVisible(true)} popup />
            <QuickAddSheet visible={addVisible} onClose={() => setAddVisible(false)} />
        </div>
    );
}
