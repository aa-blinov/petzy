import { useState, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { useInfiniteQuery } from '@tanstack/react-query';
import { ActionSheet, Button, FloatingBubble } from 'antd-mobile';
import { AddOutline, FilterOutline } from 'antd-mobile-icons';
import { tilesConfig } from '../utils/tilesConfig';
import { historyConfig } from '../utils/historyConfig';
import { usePetTilesSettings } from '../hooks/usePetTilesSettings';
import { usePet } from '../hooks/usePet';
import { hapticFeedback } from '../utils/haptic';
import { healthRecordsService } from '../services/healthRecords.service';
import { HistoryItem } from '../components/HistoryItem';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { NextDoseWidget } from '../components/NextDoseWidget';

export function Dashboard() {
  const navigate = useNavigate();
  const { selectedPetId, selectedPetName } = usePet();
  const { tilesSettings } = usePetTilesSettings(selectedPetId);

  const [actionSheetVisible, setActionSheetVisible] = useState(false);
  const [filterSheetVisible, setFilterSheetVisible] = useState(false);
  const [filter, setFilter] = useState<string>('all');

  const pageSize = 20;

  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
    error
  } = useInfiniteQuery({
    queryKey: ['timeline', selectedPetId, filter],
    queryFn: async ({ pageParam = 1 }) => {
      if (!selectedPetId) return { items: [], page: 1, total: 0, hasMore: false };
      const response = await healthRecordsService.getTimeline(
        selectedPetId,
        pageParam as number,
        pageSize,
        filter
      );
      return {
        items: response.items || [],
        page: response.page,
        total: response.total,
        hasMore: response.page * pageSize < response.total
      };
    },
    getNextPageParam: (lastPage) => (lastPage.hasMore ? lastPage.page + 1 : undefined),
    initialPageParam: 1,
    enabled: !!selectedPetId
  });

  const visibleTiles = useMemo(() => tilesConfig
    .filter(tile => tile.isTile !== false && tilesSettings.visible[tile.id] !== false)
    .sort((a, b) => {
      const aI = tilesSettings.order.indexOf(a.id);
      const bI = tilesSettings.order.indexOf(b.id);
      return (aI === -1 ? 999 : aI) - (bI === -1 ? 999 : bI);
    }), [tilesSettings]);

  const addActions = useMemo(() => visibleTiles.map(tile => ({
    text: tile.title,
    key: tile.id,
    onClick: () => {
      hapticFeedback('light');
      if (tile.screen.includes('-form')) navigate(`/form/${tile.id}`);
    }
  })), [visibleTiles, navigate]);

  const filterActions = useMemo(() => [
    {
      text: 'Все события',
      key: 'all',
      onClick: () => { hapticFeedback('light'); setFilter('all'); }
    },
    ...visibleTiles.map(tile => ({
      text: tile.title,
      key: tile.id,
      onClick: () => { hapticFeedback('light'); setFilter(tile.id); }
    }))
  ], [visibleTiles]);

  const currentFilterTitle =
    filter === 'all'
      ? 'Все события'
      : visibleTiles.find(t => t.id === filter)?.title ?? 'Все события';

  const allItems = data?.pages.flatMap(page => page.items) ?? [];

  const groupedItems = useMemo(() => {
    return allItems.reduce<Record<string, any[]>>((acc, item) => {
      const dateStr = String(item.date_time ?? '').split(' ')[0];
      if (!acc[dateStr]) acc[dateStr] = [];
      acc[dateStr].push(item);
      return acc;
    }, {});
  }, [allItems]);

  const formatDateHeader = (dateStr: string) => {
    const parts = dateStr.split('-');
    if (parts.length !== 3) return dateStr;
    
    // Check if it's today or yesterday
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(today.getDate() - 1);
    
    // Format to YYYY-MM-DD for comparison (handling timezone offsets roughly)
    const pad = (n: number) => n.toString().padStart(2, '0');
    const todayStr = `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`;
    const yesterdayStr = `${yesterday.getFullYear()}-${pad(yesterday.getMonth() + 1)}-${pad(yesterday.getDate())}`;

    if (dateStr === todayStr) return 'Сегодня';
    if (dateStr === yesterdayStr) return 'Вчера';
    
    return `${parts[2]}.${parts[1]}.${parts[0]}`;
  };

  return (
    <>
      {/* ─── Main scrollable content ─── */}
      <div className="page-container" style={{ paddingBottom: '80px' }}>
        <div className="max-width-container">

          {/* Header & Filter button */}
          <div
            className="safe-area-padding"
            style={{
              marginBottom: 'var(--spacing-md)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              minHeight: '40px',
              paddingTop: 'var(--spacing-md)'
            }}
          >
            <h2 style={{ color: 'var(--app-text-color)', fontSize: 'var(--text-xxl)', fontWeight: 600, margin: 0 }}>
              {selectedPetName ? `Лента ${selectedPetName}` : 'Лента'}
            </h2>

            <Button
              size="small"
              fill="none"
              onClick={() => setFilterSheetVisible(true)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                padding: '4px 8px',
                backgroundColor: 'var(--app-card-background)',
                borderRadius: '16px',
                boxShadow: 'var(--app-shadow-light)',
                color: 'var(--app-text-color)'
              }}
            >
              <FilterOutline />
              {currentFilterTitle}
            </Button>
          </div>

          {/* Timeline Content */}
          <div className="safe-area-padding" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {/* Widget for upcoming medication block */}
            <div style={{ paddingBottom: '8px' }}>
              <NextDoseWidget />
            </div>

            {isLoading ? (
              <LoadingSpinner fullscreen={false} />
            ) : error ? (
              <p style={{ color: 'var(--app-danger-color)', textAlign: 'center', padding: '32px 0' }}>
                Ошибка загрузки данных
              </p>
            ) : allItems.length === 0 ? (
              <p style={{ color: 'var(--app-text-secondary)', textAlign: 'center', padding: '32px 0' }}>
                Ваша лента пока пуста. Нажмите + чтобы добавить запись.
              </p>
            ) : (
              <>
                {Object.entries(groupedItems).map(([dateStr, itemsForDate]) => (
                  <div key={dateStr} style={{ marginBottom: '16px' }}>
                    {/* Date separator */}
                    <div
                      style={{
                        marginBottom: '8px',
                        marginTop: '8px',
                        fontSize: 'var(--text-md)',
                        fontWeight: 600,
                        color: 'var(--app-text-secondary)',
                        paddingLeft: '4px'
                      }}
                    >
                      {formatDateHeader(dateStr)}
                    </div>

                    {/* Cards for the day */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                      {itemsForDate.map((item: any) => {
                        const config = historyConfig[item.record_type as keyof typeof historyConfig];
                        if (!config) return null;
                        return (
                          <HistoryItem
                            key={item._id}
                            item={item}
                            config={config}
                            type={item.record_type}
                            activeTab={item.record_type}
                          />
                        );
                      })}
                    </div>
                  </div>
                ))}

                {hasNextPage && (
                  <div style={{ marginTop: '12px', display: 'flex', justifyContent: 'center', paddingBottom: '24px' }}>
                    <Button
                      fill="outline"
                      onClick={() => { fetchNextPage(); }}
                      disabled={isFetchingNextPage}
                      loading={isFetchingNextPage}
                    >
                      {isFetchingNextPage ? 'Загрузка...' : 'Загрузить еще'}
                    </Button>
                  </div>
                )}
              </>
            )}
          </div>

        </div>
      </div>

      {/* ─── FAB: rendered in portal to completely escape any CSS containing blocks ─── */}
      {createPortal(
        <FloatingBubble
          style={{
            '--initial-position-bottom': '80px',
            '--initial-position-right': '24px',
            '--edge-distance': '24px',
            '--size': '56px',
            '--background': 'var(--adm-color-primary)',
            '--border-radius': '28px',
            boxShadow: '0 4px 16px rgba(0,0,0,0.25)',
            zIndex: 200,
          } as React.CSSProperties}
          onClick={() => {
            hapticFeedback('medium');
            setActionSheetVisible(true);
          }}
        >
          <AddOutline fontSize={28} color="#ffffff" />
        </FloatingBubble>,
        document.body
      )}

      {/* Add Record ActionSheet */}
      <ActionSheet
        visible={actionSheetVisible}
        actions={addActions}
        onClose={() => setActionSheetVisible(false)}
        closeOnAction
        cancelText="Отмена"
      />

      {/* Filter ActionSheet */}
      <ActionSheet
        visible={filterSheetVisible}
        actions={filterActions}
        onClose={() => setFilterSheetVisible(false)}
        closeOnAction
        cancelText="Отмена"
      />
    </>
  );
}
