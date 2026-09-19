import { useState, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { useInfiniteQuery } from '@tanstack/react-query';
import { Button, FloatingBubble } from 'antd-mobile';
import { AddOutline } from 'antd-mobile-icons';

import { historyConfig } from '../utils/historyConfig';
import { usePet } from '../hooks/usePet';
import { hapticFeedback } from '../utils/haptic';
import { healthRecordsService } from '../services/healthRecords.service';
import { HistoryItem } from '../components/HistoryItem';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { NextDoseWidget } from '../components/NextDoseWidget';
import { PetSummaryCard } from '../components/PetSummaryCard';
import { QuickAddSheet } from '../components/QuickAddSheet';

export function Dashboard() {
  const navigate = useNavigate();
  const { selectedPetId, getSelectedPet } = usePet();

  const [actionSheetVisible, setActionSheetVisible] = useState(false);

  const pageSize = 20;

  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
    error
  } = useInfiniteQuery({
    queryKey: ['timeline', selectedPetId],
    queryFn: async ({ pageParam = 1 }) => {
      if (!selectedPetId) return { items: [], page: 1, total: 0, hasMore: false };
      const response = await healthRecordsService.getTimeline(
        selectedPetId,
        pageParam as number,
        pageSize,
        // No filtering — the timeline shows every event in chronological order.
        'all'
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

    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(today.getDate() - 1);

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

          {/* Timeline Content */}
          <div className="safe-area-padding" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {/* Pet at-a-glance summary */}
            {getSelectedPet && (
              <PetSummaryCard
                pet={getSelectedPet}
                onQuickAdd={(tileId) => {
                  hapticFeedback('light');
                  navigate(`/form/${tileId}`);
                }}
              />
            )}

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
              <div style={{
                textAlign: 'center',
                padding: '32px 16px',
                color: 'var(--app-text-secondary)',
              }}>
                <p style={{ marginBottom: '16px', fontSize: '15px' }}>
                  Лента пока пуста — запишите первое событие
                </p>
                <Button
                  color="primary"
                  size="middle"
                  onClick={() => setActionSheetVisible(true)}
                >
                  <AddOutline /> &nbsp;Добавить запись
                </Button>
              </div>
            ) : (
              <>
                {Object.entries(groupedItems).map(([dateStr, itemsForDate]) => (
                  <div key={dateStr} style={{ marginBottom: '16px' }}>
                    {/* Date separator */}
                    <h3
                      className="section-header"
                      style={{
                        marginBottom: '10px',
                        marginTop: '4px',
                        paddingLeft: '4px',
                      }}
                    >
                      {formatDateHeader(dateStr)}
                    </h3>

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

      {/* ─── FAB: rendered in portal to completely escape any CSS containing blocks.
           Actual positioning lives in globals.css under .adm-floating-bubble so
           it pins to the bottom-right even as antd-mobile's component logic
           sets its own transforms. ─── */}
      {createPortal(
        <FloatingBubble
          style={{
            '--edge-distance': '24px',
            '--size': '56px',
            '--background': 'var(--app-primary-color)',
            '--border-radius': '28px',
            boxShadow: '0 4px 16px rgba(196, 106, 63, 0.45)',
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

      {/* Add Record — quick-add grid */}
      <QuickAddSheet
        visible={actionSheetVisible}
        onClose={() => setActionSheetVisible(false)}
      />
    </>
  );
}
