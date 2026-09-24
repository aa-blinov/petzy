import { useState, useMemo, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Navigate, useNavigate } from 'react-router-dom';
import { useInfiniteQuery } from '@tanstack/react-query';
import { Button, FloatingBubble, PullToRefresh } from 'antd-mobile';
import { AddOutline } from 'antd-mobile-icons';
import { PawPrint } from 'lucide-react';

import { buildEventDisplayConfigs } from '../utils/eventDisplay';
import { useEventTypes } from '../hooks/useEventTypes';
import { usePet } from '../hooks/usePet';
import { useSession } from '../hooks/useSession';
import { isOnboardingDismissed } from '../utils/onboarding';
import { hapticFeedback } from '../utils/haptic';
import { healthRecordsService, type HealthRecord } from '../services/healthRecords.service';
import { HistoryItem } from '../components/HistoryItem';
import { DashboardSkeleton } from '../components/Skeletons';
import { NextDoseWidget } from '../components/NextDoseWidget';
import { PetSummaryCard } from '../components/PetSummaryCard';
import { QuickAddSheet } from '../components/QuickAddSheet';
import { EmptyState } from '../components/EmptyState';

export function Dashboard() {
  const navigate = useNavigate();
  const { selectedPetId, getSelectedPet, pets, isFetched: petsFetched } = usePet();
  const { username } = useSession();
  const { eventTypes } = useEventTypes();
  const historyConfig = useMemo(() => buildEventDisplayConfigs(eventTypes), [eventTypes]);

  const [actionSheetVisible, setActionSheetVisible] = useState(false);

  // FloatingBubble is draggable (@use-gesture/react under the hood), and
  // — even for a plain tap with zero movement — the gesture library's own
  // pointerdown handling stops the browser from ever synthesizing the
  // follow-up "click" event: pointerdown and pointerup both fire, but
  // click never does, so the `onClick` prop antd-mobile exposes silently
  // never runs and the button reads as dead. Track the tap ourselves from
  // the pointer events that do fire reliably, and open the sheet only if
  // the pointer barely moved (a real drag reports here too, but with far
  // more travel than a finger/cursor wobbles on a tap).
  const fabTapStart = useRef<{ x: number; y: number } | null>(null);
  useEffect(() => {
    const button = document.querySelector<HTMLElement>('.adm-floating-bubble-button');
    if (!button) return;

    const onPointerDown = (e: PointerEvent) => {
      fabTapStart.current = { x: e.clientX, y: e.clientY };
    };
    const onPointerUp = (e: PointerEvent) => {
      const start = fabTapStart.current;
      fabTapStart.current = null;
      if (!start) return;
      if (Math.hypot(e.clientX - start.x, e.clientY - start.y) < 6) {
        hapticFeedback('medium');
        setActionSheetVisible(true);
      }
    };

    button.addEventListener('pointerdown', onPointerDown);
    button.addEventListener('pointerup', onPointerUp);
    return () => {
      button.removeEventListener('pointerdown', onPointerDown);
      button.removeEventListener('pointerup', onPointerUp);
    };
  }, []);

  const pageSize = 20;

  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
    error,
    refetch,
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

  const allItems = useMemo(() => data?.pages.flatMap(page => page.items) ?? [], [data]);

  const groupedItems = useMemo(() => {
    return allItems.reduce<Record<string, HealthRecord[]>>((acc, item) => {
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

  // A brand-new account lands here with nothing to show: send it through
  // onboarding (which ends by adding the first pet). Someone who opted to
  // wait for a shared pet instead gets a plain explanation, not a feed
  // that offers to log events for a pet that doesn't exist.
  if (petsFetched && pets.length === 0) {
    if (!isOnboardingDismissed(username)) return <Navigate to="/welcome" replace />;
    return (
      <div className="page-container">
        <div className="max-width-container">
          <EmptyState
            icon={PawPrint}
            title="Питомцев пока нет"
            description={`Когда с вами поделятся питомцем, он появится здесь. Ваш логин: ${username ?? ''}`}
            actionLabel="Добавить своего"
            onAction={() => navigate('/welcome')}
          />
        </div>
      </div>
    );
  }

  return (
    <>
      {/* ─── Main scrollable content ─── */}
      <div className="page-container" style={{ paddingBottom: '80px' }}>
        <div className="max-width-container">
          <PullToRefresh
            onRefresh={async () => {
              hapticFeedback('medium');
              await refetch();
            }}
            headHeight={48}
          >

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
              <DashboardSkeleton />
            ) : error ? (
              <p style={{ color: 'var(--app-danger-color)', textAlign: 'center', padding: '32px 0' }}>
                Не удалось загрузить данные
              </p>
            ) : allItems.length === 0 ? (
              <div style={{
                textAlign: 'center',
                padding: '32px 16px',
                color: 'var(--app-text-secondary)',
              }}>
                <p style={{ marginBottom: '16px', fontSize: '15px' }}>
                  Лента пока пуста. Запишите первое событие
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
                      {itemsForDate.map((item: HealthRecord) => {
                        if (!item.record_type) return null;
                        const config = historyConfig[item.record_type];
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
                      {isFetchingNextPage ? 'Загрузка...' : 'Загрузить ещё'}
                    </Button>
                  </div>
                )}
              </>
            )}
          </div>
          </PullToRefresh>

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
