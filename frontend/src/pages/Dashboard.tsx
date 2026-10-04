import { useEffect, useRef, useState, useMemo, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { Navigate, useNavigate } from 'react-router-dom';
import { useInfiniteQuery } from '@tanstack/react-query';
import { Button, PullToRefresh } from 'antd-mobile';
import { AddOutline } from 'antd-mobile-icons';
import { PawPrint } from 'lucide-react';

import { buildEventDisplayConfigs } from '../utils/eventDisplay';
import { useEventTypes } from '../hooks/useEventTypes';
import { usePet } from '../hooks/usePet';
import { useSession } from '../hooks/useSession';
import { hadPets, isOnboardingDismissed, rememberHavingPets } from '../utils/onboarding';
import { hapticFeedback } from '../utils/haptic';
import { healthRecordsService, type HealthRecord } from '../services/healthRecords.service';
import { HistoryItem } from '../components/HistoryItem';
import { useHiddenRecords } from '../utils/deferredDelete';
import { DashboardSkeleton } from '../components/Skeletons';
import { NextDoseWidget } from '../components/NextDoseWidget';
import { PendingIntakesNotice } from '../components/PendingIntakesNotice';
import { PetSummaryCard } from '../components/PetSummaryCard';
import { QuickAddSheet } from '../components/QuickAddSheet';
import { EmptyState } from '../components/EmptyState';
import { LoadError } from '../components/LoadError';
import { PendingInvites } from '../components/PendingInvites';
import { usePetInvites } from '../hooks/usePetInvites';

/** The next page comes when the end of the list comes near (the button stays, for whoever uses it). */
function AutoLoadMore({ onVisible, disabled, children }: { onVisible: () => void; disabled: boolean; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const latest = useRef(onVisible);
  useEffect(() => {
    latest.current = onVisible;
  });
  useEffect(() => {
    const el = ref.current;
    if (!el || disabled || typeof IntersectionObserver === 'undefined') return;
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) latest.current();
    }, { rootMargin: '300px' });
    observer.observe(el);
    return () => observer.disconnect();
  }, [disabled]);
  return <div ref={ref}>{children}</div>;
}

/** Said once, on the first record: how a record is changed or deleted without opening it. */
const SWIPE_HINT_KEY = 'petzy:swipeHintSeen';

export function Dashboard() {
  const navigate = useNavigate();
  const { selectedPetId, getSelectedPet, pets, isFetched: petsFetched, isError: petsFailed, refetchPets } = usePet();
  const { username } = useSession();
  const { eventTypes } = useEventTypes();
  const historyConfig = useMemo(() => buildEventDisplayConfigs(eventTypes), [eventTypes]);

  const [actionSheetVisible, setActionSheetVisible] = useState(false);
  const [swipeHintSeen, setSwipeHintSeen] = useState(() => {
    try {
      return localStorage.getItem(SWIPE_HINT_KEY) === '1';
    } catch {
      return true;
    }
  });
  const invites = usePetInvites();
  useEffect(() => {
    if (pets.length > 0) rememberHavingPets(username);
  }, [pets.length, username]);


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
    enabled: !!selectedPetId,
    // What another person wrote while the app was in the background is there when it comes back to the front.
    refetchOnWindowFocus: true,
  });

  // Records deleted a moment ago, «Отменить» still on offer, are left out.
  const hiddenRecords = useHiddenRecords();
  const allItems = useMemo(
    () => (data?.pages.flatMap(page => page.items) ?? []).filter(item => !hiddenRecords.has(item._id)),
    [data, hiddenRecords],
  );

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
  // The roster didn't load: that says nothing about whether there are
  // pets, so no onboarding and no «Питомцев пока нет».
  if (petsFailed) {
    return (
      <div className="page-container">
        <div className="max-width-container">
          <h1 className="sr-only">Лента</h1>
          <LoadError what="питомцев" onRetry={refetchPets} />
        </div>
      </div>
    );
  }

  if (petsFetched && pets.length === 0) {
    // Someone invited to a family's pet answers that first, instead of
    // being walked through adding a pet of their own.
    if (!invites.isFetched) return <DashboardSkeleton />;
    if ((invites.data?.length ?? 0) > 0) {
      return (
        <div className="page-container">
          <div className="max-width-container safe-area-padding">
            <h1 className="sr-only">Лента</h1>
            <PendingInvites />
            <Button block fill="none" onClick={() => navigate('/welcome')}>
              Добавить своего питомца
            </Button>
          </div>
        </div>
      );
    }
    const lostAccess = hadPets(username);
    if (!isOnboardingDismissed(username) && !lostAccess) return <Navigate to="/welcome" replace />;
    return (
      <div className="page-container">
        <div className="max-width-container">
          <h1 className="sr-only">Лента</h1>
          <EmptyState
            icon={PawPrint}
            title={lostAccess ? 'Доступ к питомцу закрыт' : 'Питомцев пока нет'}
            description={
              lostAccess
                ? `Владелец закрыл вам доступ или удалил питомца. Если с вами поделятся снова, он появится здесь. Ваш логин: ${username ?? ''}`
                : `Когда с вами поделятся питомцем, он появится здесь. Ваш логин: ${username ?? ''}`
            }
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
          {/* The feed has no visible title (the tab says where you are),
              but a screen reader still needs the page's h1. */}
          <h1 className="sr-only">Лента</h1>
          <PullToRefresh
            onRefresh={async () => {
              hapticFeedback('medium');
              await refetch();
            }}
            headHeight={48}
          >

          {/* Timeline Content */}
          <div className="safe-area-padding" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <PendingInvites />
            {/* Pet at-a-glance summary */}
            {getSelectedPet && (
              <PetSummaryCard pet={getSelectedPet} />
            )}

            {/* Widget for upcoming medication block */}
            <div style={{ paddingBottom: '8px' }}>
              <PendingIntakesNotice />
              <NextDoseWidget />
            </div>

            {isLoading ? (
              <DashboardSkeleton />
            ) : error ? (
              <LoadError what="ленту" onRetry={refetch} />
            ) : allItems.length === 0 ? (
              <div style={{
                textAlign: 'center',
                padding: '32px 16px',
                color: 'var(--app-text-secondary)',
              }}>
                {/* One way to add, the round «+», not two buttons for one action on one screen. */}
                <p style={{ margin: 0, fontSize: '15px' }}>
                  Лента пока пуста. Нажмите «+», чтобы записать первое событие
                </p>
              </div>
            ) : (
              <>
                {!swipeHintSeen && (
                  <div
                    role="note"
                    style={{
                      margin: '0 0 12px',
                      padding: '10px 12px',
                      borderRadius: 'var(--radius-md)',
                      background: 'var(--app-accent-soft)',
                      color: 'var(--app-accent-deep)',
                      fontSize: 'var(--text-sm)',
                      display: 'flex',
                      flexWrap: 'wrap',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: '8px 12px',
                    }}
                  >
                    <span style={{ flex: '1 1 14em' }}>Смахните запись влево, чтобы удалить, вправо, чтобы изменить</span>
                    {/* A button that looks like one: a bare bold word at the end of a sentence read as part of the sentence. */}
                    <button
                      type="button"
                      className="touch-target"
                      style={{
                        flexShrink: 0,
                        minHeight: 'var(--touch-min)',
                        padding: '0 18px',
                        border: '1.5px solid currentColor',
                        borderRadius: 'var(--radius-md)',
                        background: 'transparent',
                        font: 'inherit',
                        fontWeight: 600,
                        color: 'inherit',
                        cursor: 'pointer',
                      }}
                      onClick={() => {
                        setSwipeHintSeen(true);
                        try {
                          localStorage.setItem(SWIPE_HINT_KEY, '1');
                        } catch {
                          /* seen for this visit only */
                        }
                      }}
                    >
                      Понятно
                    </button>
                  </div>
                )}
                {Object.entries(groupedItems).map(([dateStr, itemsForDate]) => (
                  <div key={dateStr} style={{ marginBottom: '16px' }}>
                    {/* Date separator */}
                    <h2
                      className="section-header"
                      style={{
                        marginBottom: 'var(--spacing-sm)',
                        marginTop: '4px',
                        paddingLeft: '4px',
                      }}
                    >
                      {formatDateHeader(dateStr)}
                    </h2>

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
                  <AutoLoadMore onVisible={() => { void fetchNextPage(); }} disabled={isFetchingNextPage}>
                    <div style={{ display: 'flex', justifyContent: 'center', paddingBottom: 'var(--spacing-xl)' }}>
                      <Button
                        fill="outline"
                        color="primary"
                        onClick={() => { fetchNextPage(); }}
                        disabled={isFetchingNextPage}
                        loading={isFetchingNextPage}
                      >
                        {isFetchingNextPage ? 'Загрузка...' : 'Загрузить ещё'}
                      </Button>
                    </div>
                  </AutoLoadMore>
                )}
              </>
            )}
          </div>
          </PullToRefresh>

        </div>
      </div>

      {/* FAB in a portal so no page-level containing block (route
          transitions, pull-to-refresh) can re-anchor its fixed position.
          A real button: antd's FloatingBubble was a div that only
          opened on pointer events, so a keyboard or screen reader
          could never add a record. */}
      {createPortal(
        <button
          type="button"
          className="app-fab"
          aria-label="Добавить запись"
          aria-haspopup="dialog"
          onClick={() => setActionSheetVisible(true)}
        >
          <AddOutline fontSize={28} aria-hidden />
        </button>,
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
